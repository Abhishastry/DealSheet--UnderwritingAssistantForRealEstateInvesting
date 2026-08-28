"""Neighborhood pricing signal -- spec.md Section 4a. Pure math/SQL, no LLM.

"Neighborhood" = a 0.4mi radius around the property (matching the comp
example already in design/deal-feed-mock.html), not zip code or a boundary
dataset we don't have. Computed directly from address_lat/address_lng.

Known limitation: we don't currently store RentCast's propertyType (dropped
during ingestion), so land parcels can't be excluded from the comp set
directly -- using listing_sqft IS NOT NULL as a proxy (land parcels have no
sqft), not a real property-type filter. Worth adding propertyType to the
schema properly later; flagged, not blocking this pass.
"""

import math
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property import Property

RADIUS_MILES = 0.4
# Minimum comps within the radius to call the resulting average trustworthy
# enough for a "likely" confidence tag rather than "unconfirmed" -- see the
# open item in spec.md Section 9 (exact floor not yet decided; 3 is a
# starting point, adjust once real coverage is observed).
MIN_COMPS_FOR_LIKELY_CONFIDENCE = 3


def _bounding_box(lat: float, lng: float, radius_miles: float) -> tuple[float, float, float, float]:
    """Rough lat/lng box containing the radius circle -- cheap pre-filter
    before exact haversine distance. 1 degree latitude ~= 69 miles; longitude
    degrees shrink by cos(latitude)."""
    lat_delta = radius_miles / 69.0
    lng_delta = radius_miles / (69.0 * max(math.cos(math.radians(lat)), 0.01))
    return lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r_miles * math.asin(math.sqrt(a))


def compute_neighborhood_pricing(
    session: Session, subject: Property
) -> tuple[Optional[Decimal], int, bool]:
    """Returns (pct_below_neighborhood_avg, comp_count, is_high_confidence).

    pct_below_neighborhood_avg: positive = subject is cheaper than the comp
    average (a good signal), negative = more expensive. None if no lat/lng
    or no comps found at all.
    """
    if subject.address_lat is None or subject.address_lng is None or subject.listing_ask_price is None:
        return None, 0, False

    lat, lng = float(subject.address_lat), float(subject.address_lng)
    lat_min, lat_max, lng_min, lng_max = _bounding_box(lat, lng, RADIUS_MILES)

    candidates = session.execute(
        select(Property).where(
            Property.id != subject.id,
            Property.address_lat.between(lat_min, lat_max),
            Property.address_lng.between(lng_min, lng_max),
            Property.listing_ask_price.isnot(None),
            Property.listing_sqft.isnot(None),  # crude land-parcel exclusion, see module docstring
        )
    ).scalars().all()

    comps = [
        c
        for c in candidates
        if _haversine_miles(lat, lng, float(c.address_lat), float(c.address_lng)) <= RADIUS_MILES
    ]

    if not comps:
        return None, 0, False

    avg_price = sum(float(c.listing_ask_price) for c in comps) / len(comps)
    subject_price = float(subject.listing_ask_price)
    pct_below = (avg_price - subject_price) / avg_price * 100

    return Decimal(str(round(pct_below, 2))), len(comps), len(comps) >= MIN_COMPS_FOR_LIKELY_CONFIDENCE
