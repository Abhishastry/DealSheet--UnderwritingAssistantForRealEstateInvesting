"""Fixer-tier classification + open-ended deal_reasoning generation.
spec.md Section 4a.

Split cleanly between what's deterministic (Python) and what needs an LLM:

- Neighborhood pricing (app.services.neighborhood): pure math, no LLM.
- Fixer tier: an LLM extracts structured per-item condition findings ONLY
  when there's photos/description to assess (never asked to decide the tier
  itself) -- a deterministic Python function then maps findings -> tier, per
  the degradation table in Section 4a. When there's no photos/description,
  yearBuilt alone drives a separate, pure-Python weak-signal rule -- no LLM
  call needed for that case at all.
- deal_reasoning: two guaranteed entries (neighborhood pricing, fixer tier)
  are composed in Python from real numbers/facts -- reliably well-explained
  since we control the phrasing, sort_order 0-1. The LLM generates
  additional OPEN-ENDED entries on top (sort_order 2+), informed by
  everything computed so far, per the user's explicit direction that
  deal_reasoning should not be limited to only the defined criteria.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DealReasoning, Property
from app.models.enums import DealReasoningConfidence, DealReasoningMethod, FixerTier
from app.services.neighborhood import compute_neighborhood_pricing

MODEL = "claude-sonnet-5"

FIXER_TIER_YEAR_CUTOFF = 1994  # spec.md Section 4a: "pre-~1994" proxy for light fixer


# ---- Structured output schema (client.messages.parse) ----


class CoreItemStatus(str, Enum):
    SOUND = "sound"
    DAMAGED = "damaged"
    UNKNOWN = "unknown"


class ConditionFindings(BaseModel):
    foundation: CoreItemStatus
    plumbing: CoreItemStatus
    electric: CoreItemStatus
    roof: CoreItemStatus
    structure: CoreItemStatus
    no_structure_or_foundation: bool  # true => full build, not a rehab
    floor_plan_change_needed: bool
    pool_or_fence_work: bool
    remodel_mentioned: bool


class ReasoningEntry(BaseModel):
    method: str  # validated against DealReasoningMethod below, not a strict Literal --
    # keeps the schema stable if the enum grows without touching this file.
    confidence: str
    text: str


class OpenEndedReasoning(BaseModel):
    deal_reasoning: list[ReasoningEntry]


class FullQualificationResult(BaseModel):
    condition_findings: ConditionFindings
    deal_reasoning: list[ReasoningEntry]


SYSTEM_PROMPT = """You are assisting a real-estate investor's underwriting tool for Austin-area \
fix & flip deals. You will be given structured facts about one property (and, when available, \
condition notes and/or photos) and must do two things.

1. CONDITION ASSESSMENT (only when you are given condition notes and/or photos to assess -- \
if you are not given any such material, do not attempt this and omit condition_findings).
For each of the "core 5" -- foundation, plumbing, electric, roof, structure -- assess status as:
- "sound": no negative evidence, or explicit confirmation it's fine
- "damaged": explicit evidence of a problem (visible damage, stated issue, flood/fire history)
- "unknown": genuinely no information either way
Be conservative: don't infer "sound" just because nothing was mentioned -- use "unknown" unless \
there's an actual positive signal (recent inspection note, explicit "roof replaced 2020", etc.).
Also flag: no_structure_or_foundation (true only if there is literally no structure, or the \
foundation is gone -- this is a ground-up build, not a rehab), floor_plan_change_needed, \
pool_or_fence_work (significant backyard/fence/pool work needed), remodel_mentioned (does the \
material explicitly say the property was remodeled/updated/renovated).

2. OPEN-ENDED REASONING. Generate additional "why this deal" observations beyond what's \
already been computed and given to you (you'll be told what's already covered -- don't repeat \
it). Look at everything you're given and say what a sharp analyst would actually notice: an \
unusual lot size, a notable comp pattern, a risk flag, anything genuinely relevant. Do not \
restate a fact alone -- always explain *why* it matters. Tag each entry with:
- method: one of "wholesaler_conversation", "listing_description", "photo_analysis", \
"neighborhood_analysis", or "general_analysis" (use general_analysis when an observation \
doesn't cleanly belong to one specific channel -- e.g. it combines multiple structured facts)
- confidence: "verified" (from structured/official records), "likely" (direct interpretation \
of text/photos, not confirmed), or "unconfirmed" (a claim, secondhand, or a weak/indirect \
signal) -- calibrate by cost-if-wrong, not just source type
If you have nothing genuinely notable to add beyond what's already covered, return an empty \
deal_reasoning list -- do not manufacture filler observations."""


def _build_property_facts(prop: Property) -> str:
    lines = [
        f"Address: {prop.address_street}, {prop.address_city}, TX {prop.address_zip}",
        f"County: {prop.address_county}",
        f"Ask price: ${prop.listing_ask_price}" if prop.listing_ask_price else "Ask price: unknown",
        f"Year built: {prop.listing_build_year}" if prop.listing_build_year else "Year built: unknown",
        f"Square footage: {prop.listing_sqft}" if prop.listing_sqft else "Square footage: unknown",
        f"Beds/baths: {prop.listing_beds}/{prop.listing_baths}"
        if prop.listing_beds or prop.listing_baths
        else "Beds/baths: unknown",
        f"Lot size: {prop.listing_lot_size}" if prop.listing_lot_size else "Lot size: unknown",
    ]
    return "\n".join(lines)


def _already_covered_note(pct_below: Optional[Decimal], tier: Optional[FixerTier]) -> str:
    covered = []
    if pct_below is not None:
        covered.append(f"neighborhood pricing ({pct_below}% vs. comps)")
    if tier is not None:
        covered.append(f"fixer tier ({tier.value})")
    if not covered:
        return "Nothing has been computed yet for this property -- you have a clean slate."
    return "Already computed and covered, do not repeat: " + ", ".join(covered) + "."


def compute_fixer_tier_from_findings(findings: ConditionFindings) -> tuple[FixerTier, DealReasoningConfidence]:
    """Deterministic mapping, spec.md Section 4a. Unknown counts as damaged --
    conservative default, we don't distinguish "confirmed bad" from "no info"."""
    if findings.no_structure_or_foundation:
        return FixerTier.FULL_BUILD, DealReasoningConfidence.LIKELY

    core_items = [findings.foundation, findings.plumbing, findings.electric, findings.roof, findings.structure]
    sound_count = sum(1 for item in core_items if item == CoreItemStatus.SOUND)

    if sound_count == 5:
        return FixerTier.LIGHT, DealReasoningConfidence.LIKELY
    elif sound_count >= 3:
        return FixerTier.MEDIUM, DealReasoningConfidence.LIKELY
    else:
        return FixerTier.DEEP, DealReasoningConfidence.LIKELY


def compute_fixer_tier_from_year_only(year_built: Optional[int]) -> tuple[Optional[FixerTier], Optional[DealReasoningConfidence]]:
    """spec.md Section 4a: yearBuilt alone, no photos/description -> weak signal,
    not "insufficient data" (per user direction). No LLM call needed for this case."""
    if year_built is not None and year_built < FIXER_TIER_YEAR_CUTOFF:
        return FixerTier.LIGHT, DealReasoningConfidence.UNCONFIRMED
    return None, None


def _fixer_tier_reasoning_text(tier: FixerTier, confidence: DealReasoningConfidence, prop: Property) -> str:
    if confidence == DealReasoningConfidence.UNCONFIRMED:
        return (
            f"Built {prop.listing_build_year} (pre-{FIXER_TIER_YEAR_CUTOFF}) with no condition notes or "
            f"photos available -- weak signal only, but old construction alone nudges toward a light "
            f"cosmetic fixer. Not a substitute for real condition data."
        )
    core_summary = "core systems (foundation, plumbing, electric, roof, structure) assessed from available notes/photos"
    return f"Classified as {tier.value.replace('_', ' ')} based on {core_summary}."


def run_qualification(session: Session, client: anthropic.Anthropic, prop: Property) -> int:
    """Runs the full pipeline for one property, persists results. Returns the
    number of deal_reasoning rows written (0 if there was nothing to say)."""

    pct_below, comp_count, _high_confidence = compute_neighborhood_pricing(session, prop)
    prop.pct_below_neighborhood_avg = pct_below

    has_condition_material = bool(prop.condition_notes) or bool(prop.condition_photos)

    tier: Optional[FixerTier] = None
    tier_confidence: Optional[DealReasoningConfidence] = None
    findings: Optional[ConditionFindings] = None

    facts = _build_property_facts(prop)

    if has_condition_material:
        user_content = [
            {"type": "text", "text": facts},
            {"type": "text", "text": f"Condition notes:\n{prop.condition_notes or '(none)'}"},
        ]
        for photo_url in prop.condition_photos:
            user_content.append({"type": "image", "source": {"type": "url", "url": photo_url}})

        response = client.messages.parse(
            model=MODEL,
            max_tokens=8000,
            # Classification + generation, not deep reasoning -- medium effort is
            # the right cost/quality tradeoff for this kind of high-volume task
            # (see the claude-api skill's effort guidance). Thinking is on by
            # default on Sonnet 5 even without requesting it, and it shares the
            # same max_tokens budget as the output -- too tight a ceiling here
            # is what caused the truncated-JSON failure on the first run.
            output_config={"effort": "medium"},
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
            output_format=FullQualificationResult,
        )
        result = response.parsed_output
        findings = result.condition_findings
        tier, tier_confidence = compute_fixer_tier_from_findings(findings)
        llm_entries = result.deal_reasoning
    else:
        tier, tier_confidence = compute_fixer_tier_from_year_only(prop.listing_build_year)

        covered_note = _already_covered_note(pct_below, tier)
        user_content = [{"type": "text", "text": f"{facts}\n\n{covered_note}"}]
        response = client.messages.parse(
            model=MODEL,
            max_tokens=8000,
            output_config={"effort": "medium"},
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
            output_format=OpenEndedReasoning,
        )
        llm_entries = response.parsed_output.deal_reasoning

    prop.fixer_tier = tier
    prop.fixer_tier_confidence = tier_confidence
    if tier is None:
        prop.flags = list(set(prop.flags) | {"no_condition_data"})

    sort_order = 0
    entries_to_add: list[DealReasoning] = []

    if pct_below is not None:
        direction = "below" if pct_below >= 0 else "above"
        entries_to_add.append(
            DealReasoning(
                method=DealReasoningMethod.NEIGHBORHOOD_ANALYSIS,
                confidence=DealReasoningConfidence.LIKELY if comp_count >= 3 else DealReasoningConfidence.UNCONFIRMED,
                text=(
                    f"Listed {abs(pct_below)}% {direction} the average ask price of {comp_count} comparable "
                    f"properties within 0.4mi."
                ),
                sort_order=sort_order,
            )
        )
        sort_order += 1

    if tier is not None:
        entries_to_add.append(
            DealReasoning(
                method=DealReasoningMethod.LISTING_DESCRIPTION if has_condition_material else DealReasoningMethod.GENERAL_ANALYSIS,
                confidence=tier_confidence,
                text=_fixer_tier_reasoning_text(tier, tier_confidence, prop),
                sort_order=sort_order,
            )
        )
        sort_order += 1

    valid_methods = {m.value for m in DealReasoningMethod}
    valid_confidences = {c.value for c in DealReasoningConfidence}
    for entry in llm_entries:
        if entry.method not in valid_methods or entry.confidence not in valid_confidences:
            continue  # skip anything the model returned outside our enum, rather than crash
        entries_to_add.append(
            DealReasoning(
                method=DealReasoningMethod(entry.method),
                confidence=DealReasoningConfidence(entry.confidence),
                text=entry.text,
                sort_order=sort_order,
            )
        )
        sort_order += 1

    for entry in entries_to_add:
        entry.property_id = prop.id
        session.add(entry)

    return len(entries_to_add)
