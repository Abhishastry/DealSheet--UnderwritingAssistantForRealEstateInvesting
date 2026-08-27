"""Ingest an already-saved RentCast /listings/sale sample into the properties
table — spec.md Section 2's confirmed field mapping. Local file -> DB only,
no network call to RentCast (that already happened in
scripts/rentcast_fetch_sample.py --confirm).

What this deliberately does NOT do, per the confirmed mapping and the still-open
items in spec.md Section 9:
  - Does not set condition_notes / condition_rehab_estimate / condition_photos —
    confirmed unavailable on this endpoint. Adds the "no_condition_data" flag
    instead, so it's visible why fix & flip can't run on these automatically.
  - Does not set listing_lot_size_unit — lotSize's unit isn't confirmed yet.
  - Best-effort maps listing.status via STATUS_MAP; anything unrecognized is
    left null and reported at the end, so real status strings surface from
    running this rather than being guessed in advance.
  - Idempotent: uses ON CONFLICT DO NOTHING on the (source_type,
    source_raw_reference) partial unique index, so re-running this script
    after fetching new listings never duplicates ones we already have.

Usage:
    python scripts/ingest_rentcast_sample.py scripts/output/rentcast_Austin_TX.json
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, ".")

from app.core.db import SessionLocal
from app.models import Property
from app.models.enums import ListingStatus, Persona, SourceType

STATUS_MAP = {
    "active": ListingStatus.ACTIVE,
    "pending": ListingStatus.PENDING,
    "under contract": ListingStatus.PENDING,
    "contingent": ListingStatus.PENDING,
    "off market": ListingStatus.OFF_MARKET,
    "coming soon": ListingStatus.ACTIVE,
}


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def map_record(record: dict, unmapped_statuses: Counter) -> dict:
    street = record.get("addressLine1", "")
    if record.get("addressLine2"):
        street = f"{street}, {record['addressLine2']}"

    raw_status = record.get("status")
    status = STATUS_MAP.get((raw_status or "").strip().lower())
    if raw_status and status is None:
        unmapped_statuses[raw_status] += 1

    return {
        "address_street": street,
        "address_city": record.get("city", ""),
        "address_county": record.get("county"),
        "address_zip": record.get("zipCode", ""),
        "address_lat": to_decimal(record.get("latitude")),
        "address_lng": to_decimal(record.get("longitude")),
        "source_type": SourceType.PUBLIC_LISTING,
        # Public listings don't have a wholesaler/seller counterparty the way
        # an email or text does -- seller_agent is the closest fit, since
        # RentCast's listingAgent/listingOffice fields represent that role.
        "source_persona": Persona.SELLER_AGENT,
        "source_date_received": parse_date(record.get("listedDate")) or datetime.now(timezone.utc),
        "source_raw_reference": record.get("id"),
        "listing_ask_price": to_decimal(record.get("price")),
        "listing_status": status,
        "listing_build_year": record.get("yearBuilt"),
        "listing_sqft": record.get("squareFootage"),
        "listing_lot_size": to_decimal(record.get("lotSize")),
        "listing_beds": record.get("bedrooms"),
        "listing_baths": to_decimal(record.get("bathrooms")),
        # Confirmed unavailable on /listings/sale -- see spec.md Section 2.
        "flags": ["no_condition_data"],
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/ingest_rentcast_sample.py <path-to-saved-json>")
        sys.exit(1)

    data = json.loads(open(sys.argv[1]).read())
    listings = data if isinstance(data, list) else data.get("listings", data)

    unmapped_statuses: Counter = Counter()
    rows = [map_record(r, unmapped_statuses) for r in listings]

    session = SessionLocal()
    try:
        stmt = pg_insert(Property).values(rows)
        # Must match the partial unique index exactly (ix_properties_source_type_raw_reference_unique
        # in the migration) -- both the columns AND the WHERE predicate, or Postgres can't find it
        # as a conflict target.
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["source_type", "source_raw_reference"],
            index_where=text("source_raw_reference IS NOT NULL"),
        )
        # RETURNING only yields rows actually inserted (ON CONFLICT DO NOTHING rows are
        # silently excluded from it) -- more reliable than result.rowcount, which
        # SQLAlchemy's insertmanyvalues batching can misreport for multi-row upserts.
        stmt = stmt.returning(Property.id)
        result = session.execute(stmt)
        inserted = len(result.fetchall())
        session.commit()
    finally:
        session.close()

    print(f"Attempted: {len(rows)}")
    print(f"Inserted:  {inserted}")
    print(f"Skipped (already in DB, same RentCast id): {len(rows) - inserted}")

    if unmapped_statuses:
        print("\nUnrecognized listing.status values (left null, add to STATUS_MAP once confirmed):")
        for status, count in unmapped_statuses.most_common():
            print(f"  {status!r}: {count}")
    else:
        print("\nAll listing.status values mapped cleanly.")


if __name__ == "__main__":
    main()
