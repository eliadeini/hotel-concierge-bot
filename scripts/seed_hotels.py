"""Seed the local database with a demo hotel and the prague test hotel.

Usage (from the project root, venv active):
    python -m scripts.seed_hotels --openai-key sk-...

Both hotels start on the OpenAI engine; switch one to Claude via the
/admin/hotels endpoint to test the engine swap.
"""

import argparse

from app.db import SessionLocal, init_db
from app.models.hotel_settings import AIEngineType, HotelSettings
from app.security.crypto import encrypt_key


def upsert(db, hotel_id: str, engine: AIEngineType, api_key: str, is_test: bool):
    row = db.query(HotelSettings).filter_by(hotel_id=hotel_id).one_or_none()
    if row is None:
        row = HotelSettings(hotel_id=hotel_id)
        db.add(row)
    row.ai_engine = engine
    row.api_key_encrypted = encrypt_key(api_key)
    row.is_test = is_test
    print(f"  {hotel_id}: engine={engine.value}, is_test={is_test}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--openai-key",
        default="sk-not-set",
        help="OpenAI API key to store (encrypted) for both seed hotels",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        print("Seeding hotels:")
        upsert(db, "hotel-nahariya", AIEngineType.openai, args.openai_key, False)
        upsert(db, "hotel-test-prague", AIEngineType.openai, args.openai_key, True)
        db.commit()
    finally:
        db.close()
    print("Done.")


if __name__ == "__main__":
    main()
