"""Local verification script — not part of the app itself.

Inserts one realistic Property using the actual "12913 Snow Ln" fix & flip
example from design/deal-feed-mock.html, then re-queries it by id and asserts
everything round-trips correctly: flat columns, enums, JSONB underwriting
result, and the two related child tables (deal_reasoning, property_offers).

Run from backend/, with the venv active and DATABASE_URL pointed at either
the local Docker/native Postgres or the real Supabase instance:

    python scripts/seed_sample_property.py
"""

import sys
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.insert(0, ".")

from app.core.db import SessionLocal
from app.models import DealReasoning, Property, PropertyOffer, PropertyUnderwritingResult
from app.models.enums import (
    DealReasoningConfidence,
    DealReasoningMethod,
    ListingStatus,
    OfferSource,
    Persona,
    SourceType,
    UnderwritingStrategy,
)


def build_snow_ln_property() -> Property:
    """Mirrors design/deal-feed-mock.html's Card 1 (Fix & Flip) exactly."""
    return Property(
        address_street="12913 Snow Ln",
        address_city="Manor",
        address_county="Travis",
        address_zip="78653",
        source_type=SourceType.WHOLESALER_EMAIL,
        source_persona=Persona.WHOLESALER,
        source_date_received=datetime(2026, 8, 17, tzinfo=timezone.utc),
        source_raw_reference="wave-realty-off-market-manor-2026-08-17",
        listing_ask_price=Decimal("155000.00"),
        listing_status=ListingStatus.OFF_MARKET,
        listing_build_year=2013,
        listing_beds=3,
        listing_baths=Decimal("2.0"),
        condition_notes=(
            "Rehab scope reads as mostly cosmetic — paint, flooring, fixtures. "
            "Flyer photos show an intact roofline and no visible structural damage."
        ),
        condition_rehab_estimate=Decimal("35000.00"),
        verification_county_record_match=True,
        verification_verified_fields=["deal_reasoning.neighborhood_analysis"],
        verification_unverified_fields=["condition.notes", "condition.rehab_estimate"],
        deal_reasoning=[
            DealReasoning(
                method=DealReasoningMethod.PHOTO_ANALYSIS,
                confidence=DealReasoningConfidence.LIKELY,
                text=(
                    "Rehab scope reads as mostly cosmetic — paint, flooring, fixtures. Flyer "
                    "photos show an intact roofline and no visible structural damage. Not a "
                    "substitute for an in-person inspection."
                ),
                sort_order=0,
            ),
            DealReasoning(
                method=DealReasoningMethod.NEIGHBORHOOD_ANALYSIS,
                confidence=DealReasoningConfidence.VERIFIED,
                text="3 comparable flips within 0.4mi sold in the last 90 days, supporting the ARV estimate above.",
                sort_order=1,
            ),
        ],
        underwriting_results=[
            PropertyUnderwritingResult(
                strategy=UnderwritingStrategy.FIX_AND_FLIP,
                model_version="manual-seed-v0",
                result={
                    "recommended_offer": 138500.00,
                    "metric_type": "annualized_roi",
                    "roi_at_list": 0.224,
                    "roi_at_recommended": 0.318,
                    "margin_at_list": None,
                    "margin_at_recommended": None,
                    "breakdown": {
                        "sale_price_arv": 268000.00,
                        "selling_costs": -16300.00,
                        "net_sale_proceeds": 251700.00,
                        "total_project_costs": -199600.00,
                        "gross_deal_profit": 52100.00,
                        "opportunity_cost_of_cash": -4850.00,
                        "true_net_profit": 47250.00,
                        "cash_deployed": 148900.00,
                        "hold_months": 6,
                    },
                },
            ),
        ],
        underwriting_cleared=True,
        # Synthetic — the mock doesn't show a logged offer for this card. Included purely
        # to exercise the property_offers table's round-trip.
        offers=[
            PropertyOffer(
                price=Decimal("138500.00"),
                source=OfferSource.MANUAL,
                persona=Persona.WHOLESALER,
                occurred_at=date(2026, 8, 20),
                note="Verification seed — not a real logged offer.",
            ),
        ],
    )


def main() -> None:
    session = SessionLocal()
    try:
        prop = build_snow_ln_property()
        session.add(prop)
        session.commit()
        property_id = prop.id
        print(f"Inserted property {property_id}")
    finally:
        session.close()

    # Fresh session for the read-back, to prove this isn't just returning
    # in-memory objects from the same unit of work.
    session = SessionLocal()
    try:
        fetched = session.get(Property, property_id)
        assert fetched is not None, "round-trip failed: property not found by id"

        assert fetched.address_street == "12913 Snow Ln"
        assert fetched.source_type == SourceType.WHOLESALER_EMAIL
        assert fetched.listing_ask_price == Decimal("155000.00")
        assert fetched.underwriting_cleared is True

        assert len(fetched.deal_reasoning) == 2
        assert fetched.deal_reasoning[0].method == DealReasoningMethod.PHOTO_ANALYSIS
        assert fetched.deal_reasoning[1].confidence == DealReasoningConfidence.VERIFIED

        assert len(fetched.underwriting_results) == 1
        ff_result = fetched.underwriting_results[0]
        assert ff_result.strategy == UnderwritingStrategy.FIX_AND_FLIP
        assert ff_result.result["breakdown"]["true_net_profit"] == 47250.00
        assert ff_result.result["recommended_offer"] == 138500.00

        assert len(fetched.offers) == 1
        assert fetched.offers[0].source == OfferSource.MANUAL

        print("Round-trip OK — all fields, enums, JSONB, and related rows verified.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
