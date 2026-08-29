"""Local-only inspection of any already-saved RentCast response (no network
call, no cost). Handles both list-shaped and dict-shaped top-level responses
-- generic replacement for the ad hoc summary logic that assumed a dict and
crashed on /v1/properties' list response.

Usage:
    python scripts/inspect_saved_response.py scripts/output/rentcast_records_audit.json
"""

import json
import sys

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
    if len(sys.argv) != 2:
        print("Usage: python scripts/inspect_saved_response.py <path-to-saved-json>")
        sys.exit(1)

    data = json.loads(open(sys.argv[1], encoding="utf-8").read())

    if isinstance(data, list):
        print(f"Response is a LIST with {len(data)} item(s).")
        record = data[0] if data else {}
        if len(data) > 1:
            print("(Showing structure of the first item only -- multiple items may mean this address")
            print(" matched more than one record, e.g. multiple parcels/units.)")
    else:
        print("Response is a single object (dict).")
        record = data

    print(f"\nTop-level keys ({len(record)} total):")
    for key in sorted(record.keys()):
        value = record[key]
        preview = json.dumps(value)[:80] if not isinstance(value, (dict, list)) else f"<{type(value).__name__}>"
        print(f"  - {key}: {preview}")

    for label, hints in [("Description/remarks", DESCRIPTION_HINTS), ("Permit/improvement history", IMPROVEMENT_HINTS)]:
        found: set[str] = set()
        find_hint_keys(record, hints, found)
        print(f"\n{label} field scan:")
        print(f"  -> {sorted(found) if found else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
