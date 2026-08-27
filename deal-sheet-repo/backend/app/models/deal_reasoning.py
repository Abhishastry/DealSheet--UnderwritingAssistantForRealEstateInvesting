"""`deal_reasoning[]` from spec.md Section 3 — the "why this deal" layer
(spec Section 5a). Each row is one short callout tagged with method +
confidence, calibrated by cost-if-wrong, not just source type."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import DealReasoningConfidence, DealReasoningMethod, pg_enum

if TYPE_CHECKING:
    from app.models.property import Property


class DealReasoning(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "deal_reasoning"

    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[DealReasoningMethod] = mapped_column(
        pg_enum(DealReasoningMethod, "deal_reasoning_method"), nullable=False
    )
    confidence: Mapped[DealReasoningConfidence] = mapped_column(
        pg_enum(DealReasoningConfidence, "deal_reasoning_confidence"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Explicit display order — created_at alone can tie when the LLM synthesis step
    # writes multiple callouts for one property in a single batch.
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    property: Mapped["Property"] = relationship(back_populates="deal_reasoning")
