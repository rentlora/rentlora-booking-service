import asyncio

import bcrypt
from database import AsyncSessionLocal
from models import User
from sqlalchemy import select


async def main():
    async with AsyncSessionLocal() as session:
        # 1. Reset/Ensure iyas@gmail.com is admin with password 'password'
        stmt = select(User).where(User.email == "iyas@gmail.com")
        result = await session.execute(stmt)
        user_iyas = result.scalars().first()

        password_hash = bcrypt.hashpw("password".encode(), bcrypt.gensalt(rounds=12)).decode()

        if user_iyas:
            user_iyas.role = "admin"
            user_iyas.password_hash = password_hash
            session.add(user_iyas)
            print("Successfully updated user 'iyas@gmail.com' role to 'admin' and password to 'password'")
        else:
            new_iyas = User(
                name="Iyas K",
                email="iyas@gmail.com",
                password_hash=password_hash,
                role="admin"
            )
            session.add(new_iyas)
            print("Successfully created user 'iyas@gmail.com' with role 'admin' and password 'password'")

        # 2. Also ensure a dedicated admin@rentlora.com exists
        stmt = select(User).where(User.email == "admin@rentlora.com")
        result = await session.execute(stmt)
        user_admin = result.scalars().first()

        if user_admin:
            user_admin.role = "admin"
            user_admin.password_hash = password_hash
            session.add(user_admin)
            print("Successfully updated user 'admin@rentlora.com' password to 'password'")
        else:
            new_admin = User(
                name="Default Admin",
                email="admin@rentlora.com",
                password_hash=password_hash,
                role="admin"
            )
            session.add(new_admin)
            print("Successfully created user 'admin@rentlora.com' with role 'admin' and password 'password'")

        await session.commit()
        print("Database sync completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
