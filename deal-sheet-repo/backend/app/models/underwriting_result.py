"""`underwriting_results` from spec.md Section 3 — one row per (property, strategy).

Row existence is the null/non-null signal from the spec's `{...} | null` shape,
rather than a JSON null inside a shared blob. This makes writing one strategy's
result a single-row upsert (no read-modify-write race, matters once Section 5b's
on-demand "Run underwriting" is live) and keeps `properties.underwriting_cleared`
easy to maintain from application code alongside it.

`result` is JSONB so Phase 2/5's not-yet-defined land_recreational/str shapes
can land later with zero DDL change — see app/schemas/underwriting.py for the
typed Pydantic shapes of the strategies the spec does define today.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import UnderwritingStrategy, pg_enum

if TYPE_CHECKING:
    from app.models.property import Property


class PropertyUnderwritingResult(UUIDPKMixin, Base):
    __tablename__ = "property_underwriting_results"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy: Mapped[UnderwritingStrategy] = mapped_column(
        pg_enum(UnderwritingStrategy, "underwriting_strategy"), nullable=False
    )
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    # Which underwriting logic version produced this — for future re-runs/audits.
    model_version: Mapped[Optional[str]] = mapped_column(String(50))

    property: Mapped["Property"] = relationship(back_populates="underwriting_results")

    __table_args__ = (UniqueConstraint("property_id", "strategy", name="uq_property_underwriting_strategy"),)
