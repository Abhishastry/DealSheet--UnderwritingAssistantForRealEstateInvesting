"""Closed vocabularies from spec.md Section 3, mirrored as Python enums.

Each of these also exists as a native Postgres ENUM type (created explicitly in
the initial Alembic migration) — these Python classes are what SQLAlchemy maps
columns to, and what the rest of the app imports.
"""

import enum

from sqlalchemy.dialects.postgresql import ENUM as PGEnum


def pg_enum(python_enum_cls: type[enum.Enum], pg_name: str) -> PGEnum:
    """A Postgres ENUM column type bound to `python_enum_cls`.

    create_type=False because the Alembic migration creates (and drops) the
    native Postgres enum types explicitly — autogenerate doesn't reliably
    handle enum lifecycle, so we don't let SQLAlchemy try to manage it too.
    """
    return PGEnum(python_enum_cls, name=pg_name, create_type=False, values_callable=lambda e: [m.value for m in e])


class SourceType(str, enum.Enum):
    WHOLESALER_EMAIL = "wholesaler_email"
    WHOLESALER_SMS = "wholesaler_sms"
    PUBLIC_LISTING = "public_listing"
    COUNTY_RECORD = "county_record"


class Persona(str, enum.Enum):
    WHOLESALER = "wholesaler"
    SELLER_AGENT = "seller_agent"
    BUYER_AGENT = "buyer_agent"
    SELLER = "seller"
    LENDER = "lender"
    BUILDER = "builder"
    INVESTMENT_PARTNER = "investment_partner"


class ListingStatus(str, enum.Enum):
    OFF_MARKET = "off_market"
    ACTIVE = "active"
    PENDING = "pending"


class DealReasoningMethod(str, enum.Enum):
    WHOLESALER_CONVERSATION = "wholesaler_conversation"
    LISTING_DESCRIPTION = "listing_description"
    PHOTO_ANALYSIS = "photo_analysis"
    NEIGHBORHOOD_ANALYSIS = "neighborhood_analysis"


class DealReasoningConfidence(str, enum.Enum):
    VERIFIED = "verified"
    LIKELY = "likely"
    UNCONFIRMED = "unconfirmed"


class OfferSource(str, enum.Enum):
    MANUAL = "manual"
    WHOLESALER_EMAIL = "wholesaler_email"
    WHOLESALER_SMS = "wholesaler_sms"


class UnderwritingStrategy(str, enum.Enum):
    FIX_AND_FLIP = "fix_and_flip"
    BUY_AND_HOLD = "buy_and_hold"
    LIVE_IN_FLIP = "live_in_flip"
    LAND_RECREATIONAL = "land_recreational"
    STR = "str"


class LotSizeUnit(str, enum.Enum):
    SQFT = "sqft"
    ACRES = "acres"
