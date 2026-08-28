"""Bulk pull from RentCast's property-records endpoint (/v1/properties),
mirroring the same city/state + limit=500 pattern already confirmed to work
for /listings/sale (spec.md Section 2) -- unconfirmed whether this endpoint
supports bulk queries the same way (single-address lookup was confirmed
working; bulk is a guess worth testing once, not asserted).

DELIBERATE, QUOTA-SPENDING. Dry-run by default, needs --confirm.

Usage:
    python scripts/rentcast_fetch_records_sample.py --city Austin --state TX
    python scripts/rentcast_fetch_records_sample.py --city Austin --state TX --confirm
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, ".")

from app.core.config import settings

URL = "https://api.rentcast.io/v1/properties"
DESCRIPTION_HINTS = ["description", "remarks", "publicremarks", "listingdescription"]
IMPROVEMENT_HINTS = ["permit", "improvement", "renovation", "addition", "construction"]


def find_hint_keys(obj, hints: list[str], found: set[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if any(h in key.lower() for h in hints):
                found.add(f"{path}.{key}" if path else key)
            find_hint_keys(value, hints, found, f"{path}.{key}" if path else key)
    elif isinstance(obj, list) and obj:
        find_hint_keys(obj[0], hints, found, f"{path}[0]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", default="Austin")
    parser.add_argument("--state", default="TX")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    params = {"city": args.city, "state": args.state, "limit": args.limit, "offset": args.offset}
    print(f"Request: GET {URL}")
    print(f"Params:  {params}")

    if not args.confirm:
        print("\nDRY RUN -- no request made. Re-run with --confirm to actually spend 1 RentCast API call.")
        return

    if not settings.rentcast_api_key:
        print("\nERROR: RENTCAST_API_KEY is not set in backend/.env.", file=sys.stderr)
        sys.exit(1)

    print("\n--confirm passed -- making the real request now (spends 1 call)...")
    response = requests.get(
        URL, params=params, headers={"X-Api-Key": settings.rentcast_api_key, "Accept": "application/json"}, timeout=30
    )

    if response.status_code != 200:
        print(f"\nHTTP {response.status_code}", file=sys.stderr)
        print(response.text[:2000], file=sys.stderr)
        print(
            "\n(A non-200 here means bulk city/state queries aren't supported the same way as "
            "/listings/sale for this endpoint -- single-address lookup, already confirmed working, "
            "would be the fallback, but that's 1 call per property, not viable at scale.)",
            file=sys.stderr,
        )
        sys.exit(1)

    data = response.json()
    records = data if isinstance(data, list) else data.get("properties", data)

    out_dir = Path("scripts/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rentcast_records_{args.city}_{args.state}.json"
    out_path.write_text(json.dumps(data, indent=2))

    count = len(records) if isinstance(records, list) else "unknown (unexpected shape)"
    print(f"\nSaved raw response to {out_path}")
    print(f"Record count: {count}")

    if isinstance(records, list) and records:
        first = records[0]
        print(f"\nTop-level keys on first record ({len(first)} total):")
        for key in sorted(first.keys()):
            print(f"  - {key}")

        # Presence/non-null across ALL records, same completeness check as
        # inspect_rentcast_sample.py did for /listings/sale.
        presence: Counter = Counter()
        non_null: Counter = Counter()
        for r in records:
            for key, value in r.items():
                presence[key] += 1
                if value not in (None, "", [], {}):
                    non_null[key] += 1

        print(f"\n{'field':<25} {'present':>10} {'non-null':>10}")
        for key in sorted(presence, key=lambda k: -presence[k]):
            print(f"{key:<25} {presence[key]:>6}/{len(records)} {non_null[key]:>7}/{len(records)}")

        for label, hints in [("Description/remarks", DESCRIPTION_HINTS), ("Permit/improvement history", IMPROVEMENT_HINTS)]:
            found: set[str] = set()
            for r in records:
                find_hint_keys(r, hints, found)
            print(f"\n{label} field scan (across all records):")
            print(f"  -> {sorted(found) if found else 'NOT FOUND on any record'}")


if __name__ == "__main__":
    main()
