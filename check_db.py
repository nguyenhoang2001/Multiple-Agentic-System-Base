import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mars"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        result = await session.execute(text("SELECT role, COUNT(*) FROM chat_messages GROUP BY role"))
        for row in result:
            print(f"Role: {row[0]}, Count: {row[1]}")

asyncio.run(main())
