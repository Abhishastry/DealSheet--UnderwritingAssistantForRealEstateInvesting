"""The core `properties` table — spec.md Section 3's Property object.

`address`, `source`, `listing`, `condition`, and `verification` are all
singular/scalar per the spec, so they're flat columns here rather than child
tables. The list-shaped parts of the spec (`offer_history[]`,
`deal_reasoning[]`, `underwriting_results`) live in their own modules as
child tables — see offer.py, deal_reasoning.py, underwriting_result.py.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ARRAY, Boolean, Index, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UpdatedAtMixin, UUIDPKMixin
from app.models.enums import ListingStatus, LotSizeUnit, Persona, SourceType, pg_enum

if TYPE_CHECKING:
    from app.models.deal_reasoning import DealReasoning
    from app.models.offer import PropertyOffer
    from app.models.underwriting_result import PropertyUnderwritingResult


class Property(UUIDPKMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "properties"

    # -- address --
    address_street: Mapped[str] = mapped_column(String(255), nullable=False)
    address_city: Mapped[str] = mapped_column(String(120), nullable=False)
    address_county: Mapped[Optional[str]] = mapped_column(String(120))
    address_zip: Mapped[str] = mapped_column(String(10), nullable=False)
    address_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    address_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))

    # -- source (singular per spec — the record's own intake channel) --
    source_type: Mapped[SourceType] = mapped_column(pg_enum(SourceType, "source_type"), nullable=False)
    source_persona: Mapped[Persona] = mapped_column(pg_enum(Persona, "persona"), nullable=False)
    source_date_received: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    source_raw_reference: Mapped[Optional[str]] = mapped_column(Text)

    # -- listing --
    listing_ask_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    listing_status: Mapped[Optional[ListingStatus]] = mapped_column(pg_enum(ListingStatus, "listing_status"))
    listing_build_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    listing_sqft: Mapped[Optional[int]] = mapped_column()
    listing_lot_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    listing_lot_size_unit: Mapped[Optional[LotSizeUnit]] = mapped_column(
        pg_enum(LotSizeUnit, "lot_size_unit")
    )
    listing_beds: Mapped[Optional[int]] = mapped_column(SmallInteger)
    listing_baths: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))

    # -- condition --
    condition_notes: Mapped[Optional[str]] = mapped_column(Text)
    condition_rehab_estimate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    condition_photos: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    condition_doc_links: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")

    # -- verification --
    verification_county_record_match: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    verification_tax_history: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Canonical field-path strings (e.g. "listing.ask_price"), validated at the app layer —
    # this vocabulary is effectively every leaf field in the schema, too broad/high-churn
    # for a DB enum or CHECK constraint.
    verification_verified_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    verification_unverified_fields: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )

    # Denormalized for the Phase 1 feed query (spec Section 5a loads this on every view).
    # Kept in sync with property_underwriting_results by app.services — see that module's
    # set_underwriting_result(), not a DB trigger, once the underwriting module exists.
    underwriting_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    flags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")

    # -- relationships --
    offers: Mapped[list["PropertyOffer"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="PropertyOffer.occurred_at"
    )
    deal_reasoning: Mapped[list["DealReasoning"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="DealReasoning.sort_order"
    )
    underwriting_results: Mapped[list["PropertyUnderwritingResult"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_properties_address_zip", "address_zip"),
        Index("ix_properties_source_type", "source_type"),
        Index("ix_properties_underwriting_cleared", "underwriting_cleared"),
        Index("ix_properties_flags_gin", "flags", postgresql_using="gin"),
        # Idempotent-ingestion insurance: cheap to add now, expensive to retrofit once
        # duplicate rows exist from Gmail/RentCast retries.
        Index(
            "ix_properties_source_type_raw_reference_unique",
            "source_type",
            "source_raw_reference",
            unique=True,
            postgresql_where=text("source_raw_reference IS NOT NULL"),
        ),
    )
