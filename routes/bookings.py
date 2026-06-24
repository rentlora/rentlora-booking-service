import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from auth import get_current_user
from database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from messaging import publish_booking_event
from models import Booking, Property, User
from notifications import send_booking_email, send_host_sms_alert
from schemas import BookingCreateRequest
from sqlalchemy import and_, case, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("booking-service.routes.bookings")
router = APIRouter(prefix="/bookings", tags=["bookings"])


def _first_image(images):
    if isinstance(images, list) and images:
        return images[0]
    return None


def _booking_detail_payload(booking: Booking, guest: User, prop: Property):
    return {
        "id": booking.id,
        "check_in": booking.check_in,
        "check_out": booking.check_out,
        "guests_count": booking.guests_count,
        "total_nights": booking.total_nights,
        "total_price": booking.total_price,
        "status": booking.status,
        "created_at": booking.created_at,
        "guest": {"id": guest.id, "name": guest.name, "email": guest.email},
        "property": {
            "id": prop.id,
            "title": prop.title,
            "city": prop.city,
            "location": prop.location,
            "price_per_night": prop.price_per_night,
            "first_image": _first_image(prop.images),
        },
    }


async def autocomplete_past_bookings(db: AsyncSession):
    today = date.today()
    stmt = select(Booking).where(and_(Booking.status == "confirmed", Booking.check_out < today))
    past = (await db.execute(stmt)).scalars().all()
    if past:
        for b in past:
            b.status = "completed"
            db.add(b)
        await db.commit()


@router.get("/my")
async def my_bookings(
    status: str = Query(default="all", pattern="^(upcoming|past|cancelled|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await autocomplete_past_bookings(db)
    # Allow any authenticated user to view bookings they created as a guest
    today = date.today()
    stmt = (
        select(Booking, Property)
        .join(Property, Property.id == Booking.property_id)
        .where(Booking.guest_id == current_user.id)
    )
    if status == "upcoming":
        stmt = stmt.where(and_(Booking.status == "confirmed", Booking.check_in >= today)).order_by(Booking.check_in.asc())
    elif status == "past":
        stmt = stmt.where(Booking.check_out < today).order_by(Booking.check_out.desc())
    elif status == "cancelled":
        stmt = stmt.where(Booking.status == "cancelled").order_by(Booking.check_out.desc())
    else:
        stmt = stmt.order_by(
            case((and_(Booking.status == "confirmed", Booking.check_in >= today), 0), else_=1),
            Booking.check_in.asc(),
            Booking.created_at.desc(),
        )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": b.id,
            "check_in": b.check_in,
            "check_out": b.check_out,
            "guests_count": b.guests_count,
            "total_nights": b.total_nights,
            "total_price": b.total_price,
            "status": b.status,
            "created_at": b.created_at,
            "property": {
                "id": p.id,
                "title": p.title,
                "city": p.city,
                "location": p.location,
                "price_per_night": p.price_per_night,
                "first_image": _first_image(p.images),
            },
        }
        for b, p in rows
    ]


@router.get("/host/mine")
async def host_bookings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "host":
        raise HTTPException(status_code=403, detail="Only hosts can access this endpoint")
    await autocomplete_past_bookings(db)
    stmt = (
        select(Booking, User, Property)
        .join(User, User.id == Booking.guest_id)
        .join(Property, Property.id == Booking.property_id)
        .where(Property.host_id == current_user.id)
        .order_by(desc(Booking.created_at))
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": b.id,
            "check_in": b.check_in,
            "check_out": b.check_out,
            "guests_count": b.guests_count,
            "total_price": b.total_price,
            "status": b.status,
            "guest": {"id": g.id, "name": g.name, "email": g.email},
            "property": {"id": p.id, "title": p.title, "city": p.city, "location": p.location, "price_per_night": p.price_per_night},
        }
        for b, g, p in rows
    ]


@router.get("/{booking_id}")
async def get_booking(booking_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await autocomplete_past_bookings(db)
    row = (
        await db.execute(
            select(Booking, User, Property)
            .join(User, User.id == Booking.guest_id)
            .join(Property, Property.id == Booking.property_id)
            .where(Booking.id == booking_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking, guest, prop = row
    if current_user.id not in (booking.guest_id, prop.host_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return _booking_detail_payload(booking, guest, prop)


@router.post("")
async def create_booking(
    payload: BookingCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "guest":
        raise HTTPException(status_code=403, detail="Only guests can create bookings")

    prop = await db.scalar(select(Property).where(Property.id == payload.property_id, Property.is_available.is_(True)))
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found or unavailable")
    if prop.host_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot book your own property")

    tomorrow = date.today() + timedelta(days=1)
    if payload.check_in < tomorrow:
        raise HTTPException(status_code=400, detail="check_in must be at least tomorrow")
    if payload.check_out <= payload.check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")
    if payload.guests_count < 1 or payload.guests_count > prop.max_guests:
        raise HTTPException(status_code=400, detail="Invalid guests_count for this property")

    overlap = await db.scalar(
        select(Booking.id).where(
            Booking.property_id == payload.property_id,
            Booking.status == "confirmed",
            ~or_(Booking.check_out <= payload.check_in, Booking.check_in >= payload.check_out),
        )
    )
    if overlap:
        logger.warning(f"Booking overlap detected for property {payload.property_id} by user {current_user.id}")
        raise HTTPException(status_code=409, detail="Property is not available for selected dates")

    total_nights = (payload.check_out - payload.check_in).days
    total_price = Decimal(total_nights) * prop.price_per_night
    platform_fee = total_price * Decimal("0.10")  # 10% platform fee
    booking = Booking(
        guest_id=current_user.id,
        property_id=payload.property_id,
        check_in=payload.check_in,
        check_out=payload.check_out,
        guests_count=payload.guests_count,
        total_nights=total_nights,
        total_price=total_price,
        platform_fee=platform_fee,
        status="confirmed",
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    logger.info(f"Booking {booking.id} created successfully for property {payload.property_id} by user {current_user.id}")

    # Trigger Asynchronous Notifications
    # Fetch host to get phone number (assuming User model has phone field, otherwise gracefully fails in dev mode)
    host = await db.scalar(select(User).where(User.id == prop.host_id))
    host_phone = getattr(host, 'phone', None)

    background_tasks.add_task(
        send_booking_email,
        user_email=current_user.email,
        user_name=current_user.name,
        property_title=prop.title,
        check_in=payload.check_in,
        check_out=payload.check_out,
        total_price=total_price
    )

    if host_phone:
        background_tasks.add_task(
            send_host_sms_alert,
            host_phone=host_phone,
            property_title=prop.title,
            check_in=payload.check_in
        )

    # Emit a booking-created event to SQS for downstream consumers
    background_tasks.add_task(
        publish_booking_event,
        "created",
        booking.id,
        user_email=current_user.email,
        property_title=prop.title,
        check_in=payload.check_in,
        check_out=payload.check_out,
        total_price=total_price,
    )

    return _booking_detail_payload(booking, current_user, prop)


@router.put("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(Booking, Property)
            .join(Property, Property.id == Booking.property_id)
            .where(Booking.id == booking_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking, prop = row
    if current_user.id not in (booking.guest_id, prop.host_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    if booking.status != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed bookings can be cancelled")
    if current_user.id == booking.guest_id:
        cutoff = datetime.now(timezone.utc) + timedelta(hours=48)
        check_in_dt = datetime.combine(booking.check_in, datetime.min.time()).replace(tzinfo=timezone.utc)
        if check_in_dt <= cutoff:
            raise HTTPException(status_code=403, detail="Guests can only cancel more than 48 hours before check-in")
    booking.status = "cancelled"
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    logger.info(f"Booking {booking.id} was cancelled by user {current_user.id}")

    # Emit a booking-cancelled event to SQS for downstream consumers
    background_tasks.add_task(
        publish_booking_event,
        "cancelled",
        booking.id,
        property_title=prop.title,
        cancelled_by=current_user.id,
    )

    guest = await db.scalar(select(User).where(User.id == booking.guest_id))
    return _booking_detail_payload(booking, guest, prop)


@router.put("/{booking_id}/complete")
async def complete_booking(booking_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = (
        await db.execute(
            select(Booking, Property)
            .join(Property, Property.id == Booking.property_id)
            .where(Booking.id == booking_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking, prop = row
    if current_user.id != prop.host_id:
        raise HTTPException(status_code=403, detail="Only the host can complete this booking")
    if booking.status != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed bookings can be completed")
    booking.status = "completed"
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    logger.info(f"Booking {booking.id} was marked as completed by host {current_user.id}")
    guest = await db.scalar(select(User).where(User.id == booking.guest_id))
    return _booking_detail_payload(booking, guest, prop)
