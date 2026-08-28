"""Batch runner for the fixer-tier + deal_reasoning pipeline (app.services.qualification).

DELIBERATE, MONEY-SPENDING script (Anthropic API calls). Dry-run by default
-- prints what it would process, makes no API calls -- needs --confirm to
actually run.

Skips properties that already have deal_reasoning rows (already processed),
so re-running after a partial batch or after ingesting new properties only
processes what's new -- safe to re-run without re-paying for old ones.

Usage:
    # Dry run -- shows how many properties would be processed, no API calls:
    python scripts/run_qualification.py

    # Test on a handful first:
    python scripts/run_qualification.py --limit 5 --confirm

    # Full run:
    python scripts/run_qualification.py --confirm
"""

import argparse
import sys

import anthropic
from sqlalchemy import select

sys.path.insert(0, ".")

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import DealReasoning, Property
from app.services.qualification import run_qualification


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="Process at most N properties.")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        already_done = {row[0] for row in session.execute(select(DealReasoning.property_id).distinct())}
        all_ids = session.execute(select(Property.id)).scalars().all()
        pending_ids = [pid for pid in all_ids if pid not in already_done]
    finally:
        session.close()

    if args.limit:
        pending_ids = pending_ids[: args.limit]

    print(f"Total properties: {len(all_ids)}")
    print(f"Already processed (skipping): {len(already_done)}")
    print(f"Pending this run: {len(pending_ids)}")

    if not args.confirm:
        print("\nDRY RUN -- no API calls made. Re-run with --confirm to actually process (spends real $).")
        return

    if not settings.anthropic_api_key:
        print("\nERROR: ANTHROPIC_API_KEY is not set in backend/.env.", file=sys.stderr)
        sys.exit(1)

    if not pending_ids:
        print("\nNothing to do -- all properties already processed.")
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    print(f"\n--confirm passed -- processing {len(pending_ids)} properties now...")
    succeeded = 0
    failed = 0
    total_entries = 0

    for i, prop_id in enumerate(pending_ids, start=1):
        session = SessionLocal()
        try:
            prop = session.get(Property, prop_id)
            if prop is None:
                continue
            entry_count = run_qualification(session, client, prop)
            session.commit()
            succeeded += 1
            total_entries += entry_count
            tier = prop.fixer_tier.value if prop.fixer_tier else "none"
            print(f"[{i}/{len(pending_ids)}] {prop.address_street}: tier={tier}, {entry_count} reasoning entries")
        except Exception as exc:  # noqa: BLE001 -- one bad property shouldn't kill the whole batch
            session.rollback()
            failed += 1
            print(f"[{i}/{len(pending_ids)}] FAILED (property {prop_id}): {exc}", file=sys.stderr)
        finally:
            session.close()

    print(f"\nDone. Succeeded: {succeeded}, Failed: {failed}, Total deal_reasoning entries written: {total_entries}")


if __name__ == "__main__":
    main()
