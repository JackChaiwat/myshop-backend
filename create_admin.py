import asyncio
from app.db.session import AsyncSessionLocal
from app.db.crud.user import create_user
from app.core.auth import hash_password


async def main():
    async with AsyncSessionLocal() as db:
        try:
            user = await create_user(db, {
                'email': 'admin@example.com',
                'hashed_password': hash_password('admin1234'),
                'full_name': 'Admin',
                'role': 'admin',
            })
            await db.commit()
            print(f'Admin created: {user.email}')
        except Exception as e:
            print(f'Error (maybe already exists): {e}')


asyncio.run(main())
