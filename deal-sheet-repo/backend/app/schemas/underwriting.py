"""Pydantic shapes for `property_underwriting_results.result` (JSONB).

fix_and_flip and buy_and_hold are the two strategies spec.md Section 3 actually
defines a breakdown for. live_in_flip, land_recreational, and str are left as
loose dicts — their real shape isn't defined until Phase 2/5 — so adding them
later is an app-layer change only, no migration.
"""

from typing import Any, Literal

from pydantic import BaseModel


class FixAndFlipResult(BaseModel):
    recommended_offer: float
    metric_type: Literal["annualized_roi"] = "annualized_roi"
    roi_at_list: float
    roi_at_recommended: float
    margin_at_list: float
    margin_at_recommended: float
    breakdown: dict[str, Any]


class BuyAndHoldResult(BaseModel):
    recommended_offer: float
    metric_type: Literal["cash_on_cash"] = "cash_on_cash"
    coc_at_list: float
    coc_at_recommended: float
    breakdown: dict[str, Any]


# Undefined in the spec until Phase 2 (live_in_flip, land_recreational) / Phase 5 (str) —
# stored as-is in the JSONB `result` column until then.
LiveInFlipResult = dict[str, Any]
LandRecreationalResult = dict[str, Any]
STRResult = dict[str, Any]
