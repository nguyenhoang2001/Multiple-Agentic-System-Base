import asyncio
import json
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def run():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT id, session_id, role, content FROM messages LIMIT 10"))
        for row in res:
            print(f"role={row.role}, content={repr(row.content)}")

asyncio.run(run())
