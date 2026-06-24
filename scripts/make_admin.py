import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import async_session_maker
from models import User
from sqlalchemy import select


async def make_admin(email: str):
    async with async_session_maker() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if not user:
            print(f"User with email {email} not found.")
            return

        if user.role == "admin":
            print(f"User {email} is already an admin.")
            return

        user.role = "admin"
        db.add(user)
        await db.commit()
        print(f"Successfully promoted {email} to admin!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(1)

    email_arg = sys.argv[1]
    asyncio.run(make_admin(email_arg))
