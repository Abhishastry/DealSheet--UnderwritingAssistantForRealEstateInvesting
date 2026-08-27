"""RentCast field audit + sample data pull — spec.md Section 2/9.

This is a DELIBERATE, QUOTA-SPENDING script. It is not run automatically by
anything else, and it will not touch the network unless you pass --confirm.

Purpose (both at once, at zero extra cost, since RentCast bills per-request
not per-record):
  1. Fetch up to 500 real listings in a single call (the max the API allows)
     to serve as real Phase 1 sample data.
  2. Inspect the ACTUAL live response shape (does it include photos? a
     description/remarks field? sale history?) so we can write an honest,
     verified field mapping into spec.md Section 3 instead of guessing.

Deliberately does NOT call /avm/value (per-property, billed separately) —
that's a later step once we're ready to compute real ARV/comps, not part of
"get some sample data in."

Usage:
    # Dry run (default) — prints exactly what would be requested, makes no call:
    python scripts/rentcast_fetch_sample.py --city Austin --state TX

    # The real call — spends 1 request against the 50/month free quota:
    python scripts/rentcast_fetch_sample.py --city Austin --state TX --confirm

Saves the raw response to scripts/output/rentcast_<city>_<state>.json for
inspection, and prints a structural summary (record count, field names on
the first record, and whether common photo/description/sale-history field
names appear anywhere in it) without dumping the whole thing to the terminal.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, ".")

from app.core.config import settings

RENTCAST_LISTINGS_URL = "https://api.rentcast.io/v1/listings/sale"

# Best-effort candidate key names to scan for in the response, purely as a
# diagnostic hint before we've confirmed the real schema — NOT an assumption
# baked into any parsing logic yet.
CANDIDATE_FIELD_HINTS = {
    "photos": ["photos", "photoUrls", "images", "imageUrls", "pictures"],
    "description": ["description", "remarks", "publicRemarks", "listingDescription"],
    "sale_history": ["history", "saleHistory", "lastSaleDate", "lastSoldDate", "priorSale"],
}


def find_hint_keys(obj, hints: list[str], found: set[str], path: str = "") -> None:
    """Recursively scan a JSON structure for keys matching any of `hints`
    (case-insensitive substring match), recording the dotted path where found."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = key.lower()
            if any(hint.lower() in key_lower for hint in hints):
                found.add(f"{path}.{key}" if path else key)
            find_hint_keys(value, hints, found, f"{path}.{key}" if path else key)
    elif isinstance(obj, list) and obj:
        find_hint_keys(obj[0], hints, found, f"{path}[0]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", default="Austin")
    parser.add_argument("--state", default="TX")
    parser.add_argument("--limit", type=int, default=500, help="Max per RentCast's API — no reason to use less.")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--confirm", action="store_true", help="Actually make the API call. Without this, dry-run only."
    )
    args = parser.parse_args()

    params = {"city": args.city, "state": args.state, "limit": args.limit, "offset": args.offset}

    print(f"Request: GET {RENTCAST_LISTINGS_URL}")
    print(f"Params:  {params}")

    if not args.confirm:
        print("\nDRY RUN — no request made. Re-run with --confirm to actually spend 1 RentCast API call.")
        return

    if not settings.rentcast_api_key:
        print("\nERROR: RENTCAST_API_KEY is not set in backend/.env. Add it, then re-run.", file=sys.stderr)
        sys.exit(1)

    print("\n--confirm passed — making the real request now (spends 1 call)...")
    response = requests.get(
        RENTCAST_LISTINGS_URL,
        params=params,
        headers={"X-Api-Key": settings.rentcast_api_key, "Accept": "application/json"},
        timeout=30,
    )

    if response.status_code != 200:
        print(f"\nERROR: HTTP {response.status_code}", file=sys.stderr)
        print(response.text[:2000], file=sys.stderr)
        sys.exit(1)

    data = response.json()
    listings = data if isinstance(data, list) else data.get("listings", data)

    out_dir = Path("scripts/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rentcast_{args.city}_{args.state}.json"
    out_path.write_text(json.dumps(data, indent=2))

    count = len(listings) if isinstance(listings, list) else "unknown (unexpected shape)"
    print(f"\nSaved raw response to {out_path}")
    print(f"Listing count: {count}")

    if isinstance(listings, list) and listings:
        first = listings[0]
        print(f"\nTop-level keys on first record ({len(first)} total):")
        for key in sorted(first.keys()):
            print(f"  - {key}")

        print("\nScanning for candidate field names (diagnostic only, not confirmed mapping):")
        for category, hints in CANDIDATE_FIELD_HINTS.items():
            found: set[str] = set()
            find_hint_keys(first, hints, found)
            if found:
                print(f"  {category}: found -> {sorted(found)}")
            else:
                print(f"  {category}: NOT found on first record (may need a different endpoint/call)")

    print(
        "\nNext step: reconcile these real fields against spec.md Section 3 and write the "
        "confirmed mapping into the spec before any further RentCast calls."
    )


if __name__ == "__main__":
    main()
