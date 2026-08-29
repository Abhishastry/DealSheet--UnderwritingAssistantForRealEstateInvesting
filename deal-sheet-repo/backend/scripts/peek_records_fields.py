"""Local-only peek at the actual contents of sparse nested fields
(features, taxAssessments) in an already-saved property-records response.
No network call, no cost -- just reading what's already saved.

Usage:
    python scripts/peek_records_fields.py scripts/output/rentcast_records_Austin_TX.json
"""

import json
import sys


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/peek_records_fields.py <path-to-saved-json>")
        sys.exit(1)

    data = json.loads(open(sys.argv[1], encoding="utf-8").read())
    records = data if isinstance(data, list) else data.get("properties", data)

    print("=== Sample 'features' contents (first 3 non-empty) ===")
    shown = 0
    for r in records:
        if r.get("features"):
            print(json.dumps(r["features"], indent=2))
            shown += 1
            if shown >= 3:
                break
    if shown == 0:
        print("(none found)")

    print("\n=== Sample 'taxAssessments' contents (first 1 non-empty, all years) ===")
    for r in records:
        if r.get("taxAssessments"):
            print(json.dumps(r["taxAssessments"], indent=2))
            break
    else:
        print("(none found)")


if __name__ == "__main__":
    main()
