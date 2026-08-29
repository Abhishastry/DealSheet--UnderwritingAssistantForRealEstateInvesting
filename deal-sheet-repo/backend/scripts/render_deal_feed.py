"""Renders the real qualified dataset into the design mock's exact visual
language -- design/deal-feed-mock.html's CSS/card structure, reused as-is,
with real data plugged in.

What's real: address, facts, verification status, fixer tier (new badge,
not in the original mock -- styled consistently with the existing `.stamp`
pattern), and every deal_reasoning entry (real Sonnet 5 output, in
sort_order).

What's an honest placeholder: the negotiation scale and underwriting
summary. Financial formulas (target ROI, ARV sourcing, cost assumptions)
are still TBD per spec.md Section 9 -- there's no formula to compute real
numbers with yet, so those sections say so instead of showing fabricated
figures. See spec.md Section 4a / Section 9.

Usage:
    python scripts/render_deal_feed.py [--out OUTPUT.html] [--limit N]

No network calls, no cost -- reads from DATABASE_URL, writes a local file.
"""

import argparse
import sys
from decimal import Decimal
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

sys.path.insert(0, ".")

from app.core.db import SessionLocal
from app.models import Property
from app.models.enums import FixerTier

MOCK_PATH = "../design/deal-feed-mock.html"

# New, minimal addition to the mock's own CSS -- styled to match the existing
# `.stamp` pattern exactly (same font/size/border treatment), not a new design.
FIXER_TIER_CSS = """
  .fixer-tier-pill {
    display: inline-flex; align-items: center; font-family: 'IBM Plex Mono', monospace;
    font-size: 9.5px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
    padding: 3px 7px; border-radius: 999px; white-space: nowrap; margin-left: 6px;
  }
  .fixer-tier-pill.light_fixer { background: #E3E9E1; color: var(--cedar-deep); }
  .fixer-tier-pill.medium_fixer { background: #F0E4C8; color: #8A6516; }
  .fixer-tier-pill.deep_fixer, .fixer-tier-pill.full_build { background: var(--rust-soft); color: var(--rust); }

  .pending-panel {
    margin-top: 14px; background: var(--stone); border: 1px dashed var(--rule);
    border-radius: 4px; padding: 14px 15px; color: var(--ink-soft); font-size: 12.5px; line-height: 1.5;
  }
  .pending-panel .pp-title {
    font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--ink-soft); margin-bottom: 6px;
  }
"""

FIXER_TIER_LABELS = {
    FixerTier.LIGHT: "Light Fixer",
    FixerTier.MEDIUM: "Medium Fixer",
    FixerTier.DEEP: "Deep Fixer",
    FixerTier.FULL_BUILD: "Full Build",
}

METHOD_LABELS = {
    "wholesaler_conversation": "Wholesaler conversation",
    "listing_description": "Listing description",
    "photo_analysis": "Photo analysis",
    "neighborhood_analysis": "Neighborhood analysis",
    "general_analysis": "General analysis",
}


def _subaddress(prop: Property) -> str:
    parts = [f"{prop.address_city}, TX {prop.address_zip}"]
    if prop.listing_beds or prop.listing_baths:
        beds = prop.listing_beds if prop.listing_beds is not None else "?"
        baths = prop.listing_baths if prop.listing_baths is not None else "?"
        parts.append(f"{beds} bd / {baths} ba")
    if prop.listing_build_year:
        parts.append(f"Built {prop.listing_build_year}")
    return " · ".join(parts)


def _why_flag_html(entry) -> str:
    method_label = METHOD_LABELS.get(entry.method.value, entry.method.value.replace("_", " ").title())
    return f"""
      <div class="why-flag">
        <div class="wf-head">
          <span class="wf-method">◆ {escape(method_label)}</span>
          <span class="wf-confidence {entry.confidence.value}">{entry.confidence.value.title()}</span>
        </div>
        <p class="wf-text">{escape(entry.text)}</p>
      </div>"""


def _card_html(prop: Property) -> str:
    unverified_class = "" if prop.verification_county_record_match else " unverified"
    verified_pill = (
        '<span class="verified-pill verified">County-verified</span>'
        if prop.verification_county_record_match
        else '<span class="verified-pill unverified">Unverified</span>'
    )

    fixer_pill = ""
    if prop.fixer_tier:
        label = FIXER_TIER_LABELS[prop.fixer_tier]
        conf_note = f" ({prop.fixer_tier_confidence.value})" if prop.fixer_tier_confidence else ""
        fixer_pill = f'<span class="fixer-tier-pill {prop.fixer_tier.value}">{escape(label)}{escape(conf_note)}</span>'

    why_flags = "".join(_why_flag_html(e) for e in sorted(prop.deal_reasoning, key=lambda e: e.sort_order))
    if not why_flags:
        why_flags = '<div class="why-flag"><p class="wf-text">No reasoning generated yet for this property.</p></div>'

    ask_price = f"${prop.listing_ask_price:,.0f}" if prop.listing_ask_price else "Ask price unknown"
    source_label = prop.source_type.value.replace("_", " ").title()

    return f"""
    <div class="card{unverified_class}">
      <div class="card-head">
        <span class="stamp">Fix &amp; Flip{fixer_pill}</span>
        {verified_pill}
      </div>
      <p class="address">{escape(prop.address_street)}</p>
      <p class="subaddress">{escape(_subaddress(prop))}</p>
      {why_flags}

      <div class="pending-panel">
        <p class="pp-title">Underwriting — not yet computed</p>
        Ask price: {escape(ask_price)}. Recommended offer, ROI, and the full underwriting breakdown
        need the financial formula chain (target ROI threshold, ARV sourcing, cost assumptions) --
        still TBD, see spec.md Section 9. Fixer tier and neighborhood pricing above are real.
      </div>

      <div class="card-footer" style="margin-top: 12px;">
        <span class="source-tag"><strong>{escape(source_label)}</strong></span>
      </div>
    </div>"""


def _listing_row_html(prop: Property) -> str:
    price = f"${prop.listing_ask_price:,.0f}" if prop.listing_ask_price else "Price unknown"
    source_label = prop.source_type.value.replace("_", " ").title()
    status = (
        '<span class="lr-status-tag done">Qualified ✓</span>'
        if prop.deal_reasoning
        else '<span class="lr-status-tag flagged">Not yet processed</span>'
    )
    return f"""
      <div class="listing-row">
        <div class="listing-row-main">
          <p class="lr-address">{escape(prop.address_street)}</p>
          <p class="lr-meta"><span>{escape(price)}</span><span>·</span><span>{escape(source_label)}</span></p>
        </div>
        <div class="lr-status">{status}</div>
      </div>"""


def render(session: Session, limit: int | None) -> str:
    query = select(Property).options(joinedload(Property.deal_reasoning))
    properties = session.execute(query).unique().scalars().all()
    properties.sort(key=lambda p: p.address_street)
    # Only render properties that have actually been through the pipeline.
    qualified = [p for p in properties if p.deal_reasoning]
    qualified.sort(key=lambda p: (p.pct_below_neighborhood_avg or Decimal("-999")), reverse=True)
    if limit:
        qualified = qualified[:limit]

    with open(MOCK_PATH, encoding="utf-8") as f:
        mock = f.read()

    style_close = mock.index("</style>")
    styled = mock[:style_close] + FIXER_TIER_CSS + mock[style_close:]

    cards_html = "\n".join(_card_html(p) for p in qualified)

    # Replace the 3 hardcoded sample cards + the "N deals cleared" topbar line
    # with real content. Splice between the known feed markers rather than
    # regex-guessing the sample HTML, so a mock edit doesn't silently break this.
    feed_start = styled.index('<div class="feed">') + len('<div class="feed">')
    feed_end = styled.index("</div>\n\n  </div>\n\n  <div class=\"browse-all-cta\">")
    styled = styled[:feed_start] + "\n" + cards_html + "\n  " + styled[feed_end:]

    styled = styled.replace(
        "<span class=\"dot\"></span> 3 deals cleared underwriting",
        f'<span class="dot"></span> {len(qualified)} properties qualified — financial underwriting pending',
    )
    styled = styled.replace(
        "<p>That's everything that cleared underwriting this week.</p>",
        f"<p>That's every property qualified so far ({len(qualified)} of {len(properties)} sourced).</p>",
    )
    styled = styled.replace("<title>Deal Feed — Mock v2</title>", "<title>Deal Feed — Live Data</title>")

    # Real All Listings rows, replacing the mock's hardcoded sample rows.
    listings_html = "\n".join(_listing_row_html(p) for p in properties)
    listings_start = styled.index('<div class="listings-list">') + len('<div class="listings-list">')
    listings_end = styled.index("\n    </div>\n  </div>\n</main>")
    styled = styled[:listings_start] + "\n" + listings_html + "\n  " + styled[listings_end:]

    return styled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="../rendered_deal_feed.html")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        html = render(session, args.limit)
    finally:
        session.close()

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
