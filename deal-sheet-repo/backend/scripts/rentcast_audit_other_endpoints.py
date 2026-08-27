"""Check whether RentCast's /avm/value or property-records endpoint carries
description/remarks text that /listings/sale (already confirmed to lack it,
spec.md Section 2) might have. DELIBERATE, QUOTA-SPENDING per call --
dry-run by default, needs --confirm.

Both endpoints are per-property (not bulk), so this defaults to reusing the
first real address from your already-saved Austin sample
(scripts/output/rentcast_Austin_TX.json) rather than needing a new one typed
in -- pass --address to override.

Usage:
    # Dry run (default) -- prints exactly what would be requested, no call:
    python scripts/rentcast_audit_other_endpoints.py --endpoint avm

    # The real call -- spends 1 request against the 50/month free quota:
    python scripts/rentcast_audit_other_endpoints.py --endpoint avm --confirm
    python scripts/rentcast_audit_other_endpoints.py --endpoint records --confirm

Honest expectation-setting: it's plausible NEITHER endpoint has description
text, for licensing reasons rather than a paywall -- MLS remarks/description
often carry stricter redistribution restrictions under IDX/VOW agreements
than structured facts (price, sqft, beds/baths) do, so RentCast may simply
not be licensed to pass it along at all, regardless of endpoint or tier.
This call is cheap enough to check anyway before assuming that.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, ".")

from app.core.config import settings

ENDPOINTS = {
    "avm": "https://api.rentcast.io/v1/avm/value",
    # Best-effort guess at the property-records path -- unconfirmed (docs were
    # unreachable from this session). If this 404s, that itself is useful
    # information -- the exact path needs checking against RentCast's actual
    # docs/dashboard on your end.
    "records": "https://api.rentcast.io/v1/properties",
}

DESCRIPTION_HINTS = ["description", "remarks", "publicremarks", "listingdescription"]


def find_hint_keys(obj, hints: list[str], found: set[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if any(h in key.lower() for h in hints):
                found.add(f"{path}.{key}" if path else key)
            find_hint_keys(value, hints, found, f"{path}.{key}" if path else key)
    elif isinstance(obj, list) and obj:
        find_hint_keys(obj[0], hints, found, f"{path}[0]")


def default_address() -> str:
    sample_path = Path("scripts/output/rentcast_Austin_TX.json")
    if not sample_path.exists():
        print(
            f"ERROR: {sample_path} not found and no --address given. "
            "Run scripts/rentcast_fetch_sample.py first, or pass --address explicitly.",
            file=sys.stderr,
        )
        sys.exit(1)
    data = json.loads(sample_path.read_text())
    listings = data if isinstance(data, list) else data.get("listings", data)
    return listings[0]["formattedAddress"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", choices=["avm", "records"], required=True)
    parser.add_argument("--address", default=None, help="Defaults to the first address in your saved sample.")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    address = args.address or default_address()
    url = ENDPOINTS[args.endpoint]
    params = {"address": address}

    print(f"Request: GET {url}")
    print(f"Params:  {params}")

    if not args.confirm:
        print("\nDRY RUN -- no request made. Re-run with --confirm to actually spend 1 RentCast API call.")
        return

    if not settings.rentcast_api_key:
        print("\nERROR: RENTCAST_API_KEY is not set in backend/.env.", file=sys.stderr)
        sys.exit(1)

    print("\n--confirm passed -- making the real request now (spends 1 call)...")
    response = requests.get(
        url, params=params, headers={"X-Api-Key": settings.rentcast_api_key, "Accept": "application/json"}, timeout=30
    )

    if response.status_code != 200:
        print(f"\nHTTP {response.status_code}", file=sys.stderr)
        print(response.text[:2000], file=sys.stderr)
        if response.status_code == 404 and args.endpoint == "records":
            print(
                "\n(A 404 here likely means the property-records path guessed in this script "
                "is wrong -- check RentCast's actual docs/dashboard for the correct endpoint path.)",
                file=sys.stderr,
            )
        sys.exit(1)

    data = response.json()
    out_dir = Path("scripts/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rentcast_{args.endpoint}_audit.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(f"\nSaved raw response to {out_path}")

    print(f"\nTop-level keys ({len(data)} total):")
    for key in sorted(data.keys()):
        print(f"  - {key}")

    found: set[str] = set()
    find_hint_keys(data, DESCRIPTION_HINTS, found)
    print("\nDescription/remarks field scan:")
    print(f"  -> {sorted(found) if found else 'NOT FOUND anywhere in this response'}")


if __name__ == "__main__":
    main()
