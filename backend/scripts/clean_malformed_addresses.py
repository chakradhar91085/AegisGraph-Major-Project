"""
One-off cleanup for Person rows ingested before clean_address() was added to
ingest_enron_postgres.py: a handful of malformed Enron headers left a stray
leading/trailing quote character on the parsed address (e.g.
"'richard.sanders@enron.com"), creating a duplicate of the real person.

Safe to run multiple times (no-op once there's nothing left to clean).
"""
import asyncio
import os
import re
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.postgres import AsyncSessionLocal
from sqlalchemy import text


def clean(addr: str) -> str:
    return re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", addr.strip().lower())


async def main():
    async with AsyncSessionLocal() as session:
        dirty = (await session.execute(text(
            "SELECT email, name FROM persons WHERE email ~ '^[^a-zA-Z0-9]' OR email ~ '[^a-zA-Z0-9]$'"
        ))).fetchall()
        print(f"Found {len(dirty)} malformed person rows.")

        for dirty_email, name in dirty:
            clean_email = clean(dirty_email)
            if clean_email == dirty_email or not clean_email:
                continue
            await session.execute(text(
                "INSERT INTO persons (email, name) VALUES (:e, :n) ON CONFLICT (email) DO NOTHING"
            ), {"e": clean_email, "n": name})
            await session.execute(text(
                "UPDATE emails SET sender_email = :clean WHERE sender_email = :dirty"
            ), {"clean": clean_email, "dirty": dirty_email})
            await session.execute(text(
                "UPDATE email_recipients SET person_email = :clean WHERE person_email = :dirty"
            ), {"clean": clean_email, "dirty": dirty_email})
            await session.execute(text(
                "DELETE FROM persons WHERE email = :dirty"
            ), {"dirty": dirty_email})
            print(f"  merged {dirty_email!r} -> {clean_email!r}")

        await session.commit()
        print("Done.")


asyncio.run(main())
