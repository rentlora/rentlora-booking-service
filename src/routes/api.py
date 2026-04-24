from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from datetime import datetime, date
from bson import ObjectId
from typing import List
from src.models.db import db

router = APIRouter()

class BookingCreateModel(BaseModel):
    property_id: str
    landlord_id: str
    tenant_id: str
    start_date: date
    end_date: date
    total_rent_due: float

class BookingOutModel(BaseModel):
    id: str
    property_id: str
    landlord_id: str
    tenant_id: str
    start_date: date
    end_date: date
    total_rent_due: float
    status: str
    payment_status: str
    created_at: datetime

class BookingStatusUpdateModel(BaseModel):
    payment_status: str
    status: str

def serialize_booking(booking: dict) -> dict:
    booking["id"] = str(booking.pop("_id"))
    return booking

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookingOutModel)
async def create_booking(booking: BookingCreateModel):
    new_booking = booking.model_dump()
    new_booking["status"] = "pending"
    new_booking["payment_status"] = "pending"
    new_booking["created_at"] = datetime.utcnow()
    
    # Convert dates to datetime for mongo compatibility
    new_booking["start_date"] = datetime.combine(new_booking["start_date"], datetime.min.time())
    new_booking["end_date"] = datetime.combine(new_booking["end_date"], datetime.min.time())

    result = await db.db.bookings.insert_one(new_booking)
    new_booking["_id"] = result.inserted_id
    
    # Convert datetimes back to date for response model validation
    new_booking["start_date"] = new_booking["start_date"].date()
    new_booking["end_date"] = new_booking["end_date"].date()
    
    return serialize_booking(new_booking)

@router.get("/tenant/{tenant_id}", response_model=List[BookingOutModel])
async def get_tenant_bookings(tenant_id: str):
    bookings_cursor = db.db.bookings.find({"tenant_id": tenant_id})
    bookings = await bookings_cursor.to_list(length=100)
    
    for b in bookings:
        b["start_date"] = b["start_date"].date() if isinstance(b["start_date"], datetime) else b["start_date"]
        b["end_date"] = b["end_date"].date() if isinstance(b["end_date"], datetime) else b["end_date"]
        
    return [serialize_booking(b) for b in bookings]

@router.get("/landlord/{landlord_id}", response_model=List[BookingOutModel])
async def get_landlord_bookings(landlord_id: str):
    bookings_cursor = db.db.bookings.find({"landlord_id": landlord_id})
    bookings = await bookings_cursor.to_list(length=100)
    
    for b in bookings:
        b["start_date"] = b["start_date"].date() if isinstance(b["start_date"], datetime) else b["start_date"]
        b["end_date"] = b["end_date"].date() if isinstance(b["end_date"], datetime) else b["end_date"]
        
    return [serialize_booking(b) for b in bookings]

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(booking_id: str):
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=400, detail="Invalid Booking ID")
        
    result = await db.db.bookings.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": "cancelled"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    return None

@router.put("/{booking_id}/status")
async def update_booking_status(booking_id: str, update: BookingStatusUpdateModel):
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=400, detail="Invalid Booking ID")
        
    result = await db.db.bookings.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {
            "payment_status": update.payment_status,
            "status": update.status
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    return {"message": "Booking status updated"}
