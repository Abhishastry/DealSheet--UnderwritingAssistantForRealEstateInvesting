"""`offer_history[]` from spec.md Section 3 — an append-only log of real
negotiating price points, child to a Property. Populates the negotiation
scale's optional third point (spec Section 5a); empty by default, only
written when a real number exists (manual log, or Phase 2/3 thread parsing)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import OfferSource, Persona, pg_enum

if TYPE_CHECKING:
    from app.models.property import Property


class PropertyOffer(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "property_offers"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[OfferSource] = mapped_column(pg_enum(OfferSource, "offer_source"), nullable=False)
    # Reuses the same Postgres `persona` enum type as properties.source_persona.
    persona: Mapped[Optional[Persona]] = mapped_column(pg_enum(Persona, "persona"))
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)

    property: Mapped["Property"] = relationship(back_populates="offers")
