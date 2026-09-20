"""
Seed locations table from data/locations.json
Run: python scripts/seed_locations.py
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import db, Location

app = create_app()

with app.app_context():
    data_path = Path(__file__).resolve().parent.parent / "data" / "locations.json"
    with open(data_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    added = 0
    for item in items:
        exists = Location.query.filter_by(
            district=item["district"], village_name=item["village_name"]
        ).first()
        if not exists:
            loc = Location(
                district=item["district"],
                village_name=item["village_name"],
                source=item.get("source", ""),
                is_active=True,
            )
            db.session.add(loc)
            added += 1
    db.session.commit()
    print(f"Seeded {added} new locations. Total now: {Location.query.count()}")