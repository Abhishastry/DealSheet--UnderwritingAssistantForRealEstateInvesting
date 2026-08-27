"""Local-only inspection of an already-saved RentCast sample (no network call,
no API cost). Run after scripts/rentcast_fetch_sample.py --confirm.

Answers: which fields actually appear across ALL records (not just the
first), how complete each field is, and what the `history` field (or any
other nested/list-shaped field) actually looks like.

Usage:
    python scripts/inspect_rentcast_sample.py scripts/output/rentcast_Austin_TX.json
"""

import json
import sys
from collections import Counter


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/inspect_rentcast_sample.py <path-to-saved-json>")
        sys.exit(1)

    data = json.loads(open(sys.argv[1]).read())
    listings = data if isinstance(data, list) else data.get("listings", data)
    total = len(listings)
    print(f"Total records: {total}\n")

    # Field presence + null-rate across ALL records, not just the first.
    presence = Counter()
    non_null = Counter()
    for record in listings:
        for key, value in record.items():
            presence[key] += 1
            if value not in (None, "", [], {}):
                non_null[key] += 1

    print(f"{'field':<20} {'present':>8} {'non-null':>9}")
    for key in sorted(presence, key=lambda k: -presence[k]):
        print(f"{key:<20} {presence[key]:>7}/{total} {non_null[key]:>8}/{total}")

    # Specifically check the fields fix & flip needs that weren't on record 0.
    print("\nChecking for beds/baths/sqft/yearBuilt under ANY plausible name:")
    candidates = ["bed", "bath", "sqft", "squarefoot", "square_foot", "yearbuilt", "year_built"]
    found_any = set()
    for record in listings:
        for key in record:
            if any(c in key.lower() for c in candidates):
                found_any.add(key)
    print(f"  -> {sorted(found_any) if found_any else 'NONE FOUND on any of the 500 records'}")

    # Show the actual shape of `history` on the first record that has a non-empty one.
    print("\nFirst non-empty `history` field found:")
    for record in listings:
        h = record.get("history")
        if h:
            print(json.dumps(h, indent=2)[:1500])
            break
    else:
        print("  -> no record had a non-empty `history` field")


if __name__ == "__main__":
    main()
