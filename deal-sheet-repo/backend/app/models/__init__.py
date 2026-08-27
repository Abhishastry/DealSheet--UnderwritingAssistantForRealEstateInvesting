"""Import every mapped model so Base.metadata sees them all — required for
Alembic's --autogenerate to detect the full schema."""

from app.models.base import Base
from app.models.deal_reasoning import DealReasoning
from app.models.offer import PropertyOffer
from app.models.property import Property
from app.models.underwriting_result import PropertyUnderwritingResult

__all__ = ["Base", "Property", "PropertyOffer", "DealReasoning", "PropertyUnderwritingResult"]
