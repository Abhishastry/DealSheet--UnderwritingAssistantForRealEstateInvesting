# Deal Sheet — Product & Technical Spec

**Product name:** Deal Sheet
**Tagline:** Underwriting assistant for Austin investors
**Status:** Draft v2 — Phase 1 scoping, UI design validated via mock
**Last updated:** 2026-08-27

---

**Design reference:** `deal-feed-mock-v2.html` — mobile-first HTML mock validating the feed layout, negotiation scale, deal-reasoning callouts, and All Listings flow described in Section 5.

---

## 1. Product Summary

An agent that helps Austin-area real estate investors find and evaluate deals fast. It is **not** an off-market lead-generation tool (no skip tracing, no cold outreach) — it focuses on deals that are already reachable: public listings and inbound wholesaler deals. The differentiator is depth and speed of underwriting across multiple investment strategies, not sourcing hidden inventory.

**Primary users:** Austin-area investors broadly (not just personal use).

**Out of scope for v1 (deferred to v2):** direct-to-seller outreach, skip tracing, probate/tax-delinquency lead lists, any off-market sourcing that requires the product to initiate contact with a seller.

---

## 2. Sourcing Layer — Three Inputs

| Priority | Source | Format | Notes |
|---|---|---|---|
| **1** | Wholesaler emails | Gmail (personal inbox, filtered) | Highly variable format — some rich text with condition notes, some just a flyer image + Drive link with almost no body text. Parser must handle both. Free, unlimited — no API quota. |
| **1** | Wholesaler texts (SMS) | Forwarded via iOS Shortcut → dedicated Gmail address | Same parser as email once forwarded. Trigger: contact-list match OR keyword match. Free, unlimited. |
| **2** | Public listings | RentCast API, free tier | See "RentCast Strategy" below. |
| **2** | County records | Travis CAD / Williamson CAD / Hays CAD (free, structured) | Used for enrichment + verification of wholesaler/listing claims (tax history, ownership, lot size, land use). Free, unlimited. |

**Golden rule:** Wholesaler-provided numbers (ARV, comps, condition claims) are always tagged `unverified` until cross-checked against county records or independent comps. This mirrors the discipline already used on the Angel Valley deal.

### Personas, not names

The product never references specific individuals (e.g. a wholesaler's name) in generated copy — it speaks in terms of **personas** in the deal process: Wholesaler, Seller Agent, Buyer Agent, Seller, Lender, Builder, Investment Partner. This keeps the product generalizable across users (other investors' contacts won't be the same people) and keeps UI copy consistent — e.g. "Wholesaler says the seller wants a fast close," not a person's name. The schema's `source.persona` field (see Section 3) captures this categorically rather than storing it only as a free-text sender name.

Similarly, **source attribution in the UI shows source *type*, not vendor brand** — "Public listing," "Wholesaler," "County records," not e.g. "RentCast." This keeps the design vendor-agnostic; swapping a listings API provider later shouldn't require any UI or copy changes.

### RentCast Strategy (verified 2026-08-26)

*Implementation detail — never surfaced to users. UI always shows source type ("Public listing"), not vendor name.*


- **Billing is per-request, not per-record.** Listings endpoints (`/listings/sale`, `/listings/rental/long-term`) return up to 500 listings per call, paginated via `limit`/`offset`. One paginated call = one request against the 50/month free quota, regardless of how many listings it returns.
- **Practical implication:** an initial bulk pull covering Travis/Williamson/Hays counties likely takes only a handful of requests (well within the free 50/month), not one request per property.
- **Ingestion pattern:** bulk-load once into Supabase, then run scheduled incremental refreshes (weekly or less often) to catch new/changed listings — a delta-check costs far fewer requests than a full re-pull. This is a Phase 3 scheduled job, not a live per-query lookup.
- **Field audit required before any bulk pull.** We do not yet have a confirmed, field-level map of what `/listings/sale`, `/avm/value`, and the property-records endpoint actually return (photos, description/remarks text, sale/transaction history, comparables shape) — see the open item in Section 9. Before spending real quota on a full bulk pull:
  1. Spend **1–2 calls only** — but since billing is per-request not per-record (above), each call should request `limit=500` (the max), never a small limit — a small limit costs the same as the max and only wastes potential coverage. Call 1: `/listings/sale` scoped to one county/city (e.g. Austin/Travis), `limit=500` — this doubles as both the field-shape audit and a real batch of sample data, at zero extra cost. Call 2 (optional): a second `/listings/sale` call scoped to a different county (Williamson or Hays), `limit=500`, for geographic spread — skip it if call 1 already shows one query can cover multiple counties. Do **not** call `/avm/value` in this pass — it's billed per-property, so ARV/comps pulls are a separate, later step once we're ready to compute real underwriting numbers, not part of getting sample data in.
  2. Reconcile those real fields against the normalized `Property` schema (Section 3) and update this spec with the confirmed mapping (what maps directly, what's missing, what needs the extraction pipeline instead of a raw field).
  3. Only after that mapping is written down do we run any further bulk pulls or the per-shortlisted-property `/avm/value` calls described above.
  This audit's 1–2 calls come out of the same 50/month free quota but are spent deliberately, before the larger ingestion, not in addition to it.
- **Coverage caveat:** RentCast targets ~96% residential listing coverage and ~90%+ for land/vacant parcels — very good, not exhaustive.
- **Value estimate endpoint** (`/avm/value`) returns an ARV-style estimate plus comparable sale listings in one call — efficient for feeding the fix-and-flip module's comp needs.
- **If free tier is outgrown:** next tier (Foundation) is $74/month for 1,000 requests (~$0.074/call) — a reasonable "value-based" upgrade once real pilot usage data justifies it. Not something to pre-solve before Phase 1.

#### Confirmed field mapping — `/listings/sale` (audited 2026-08-27, 1 real call, 500 Austin/TX records)

The field audit gate above is now satisfied for this endpoint. Actual response fields, checked across all 500 records (not just one), with two corrections to assumptions made earlier in this doc:

| `Property` schema field | RentCast field | Coverage (of 500) |
|---|---|---|
| `address.street` | `addressLine1` (+ `addressLine2` when present — unit/suite) | 500 / 208 |
| `address.city` | `city` | 500 |
| `address.county` | `county` (also `countyFips` available) | 500 |
| `address.zip` | `zipCode` | 500 |
| `address.lat` / `.lng` | `latitude` / `longitude` | 500 |
| `source.raw_reference` | `id` (RentCast's listing id; `mlsNumber` also available as a secondary reference) | 500 |
| `listing.ask_price` | `price` | 500 |
| `listing.status` | `status` — confirmed: all 500 real records mapped cleanly to `active`/`pending`/`off_market` via `{"active", "pending", "under contract", "contingent", "off market", "coming soon"}` (case-insensitive) — see `backend/scripts/ingest_rentcast_sample.py` | 500 |
| `listing.build_year` | `yearBuilt` | 382 |
| `listing.sqft` | `squareFootage` | 384 |
| `listing.lot_size` | `lotSize` — **unit not yet confirmed** (assumed sqft, not verified) | 480 |
| `listing.beds` | `bedrooms` | 399 |
| `listing.baths` | `bathrooms` | 384 |

**Correction — photos and description/remarks are NOT available on this endpoint.** No `photos`, `images`, `description`, or `remarks`-style field exists anywhere across all 500 records. This directly reverses what was assumed earlier in this doc (that listing description text + photos could feed `condition.notes`/`rehab_estimate` for RentCast-sourced deals the same way wholesaler emails do) — **that assumption was wrong.** RentCast-sourced properties genuinely cannot get a rehab estimate from `/listings/sale` alone; the earlier open question (skip fix & flip for RentCast-only deals, or add a rough $/sqft heuristic) is back open and now confirmed necessary, not hypothetical.

**`history` is listing history, not confirmed sale/closing history.** It's a dict keyed by date, each entry shaped like `{"event": "Sale Listing", "price": ..., "listingType": ..., "listedDate": ..., "removedDate": ..., "daysOnMarket": ...}` — this tracks listing/price-change events (when the property was listed, at what price), not necessarily a closed transaction with a final sale price. Whether RentCast exposes true last-sold price/date (for `verification.tax_history` or ARV context) likely requires the separate property-records endpoint mentioned in Section 9 — still unconfirmed, don't conflate the two.

**Two fields exist on the real response that aren't in our schema at all:** `hoa` (present on 252/500 — matters for buy & hold cash flow) and the MLS/agent fields (`mlsName`, `mlsNumber`, `listingAgent`, `listingOffice`). Not urgent for Phase 1's single fix & flip module, but worth a small schema extension before Phase 2's buy & hold module needs HOA for cash-on-cash math.

**Confirms the schema's "tolerate partial records" design was the right call** (Section 3): `yearBuilt`/`squareFootage`/`bedrooms`/`bathrooms` are each present on only ~77–80% of real records, `hoa` on ~50% — these are genuinely sparse fields in real data, not edge cases.

### Why not Zillow/Redfin directly

- Zillow retired its public API in 2021. The only official route (Bridge Interactive) requires MLS membership or broker credentials, is application-gated with multi-week approval, and starts around $500/month — not viable pre-broker-relationship.
- Redfin has no public developer API at all.
- Third-party "Zillow API" vendors (Zillapi, APIllow, etc.) are repackaged scrapers — buying the data from a vendor doesn't remove the ToS exposure, it just moves who's doing the scraping. Not worth the legal risk once this is a real product with users, even though data collection itself (not underwriting) is the exposed part.
- An agent auto-browsing Zillow to extract listings hits the same ToS restriction as direct scraping — automation is automation regardless of who/what is doing the browsing.
- RentCast + county records already cover the fields needed for underwriting (price, sqft, beds/baths, year built, lot size, comps). Zillow's unique value-adds (Zestimate, their specific comp engine) are nice-to-have, not need-to-have. Revisit Bridge Interactive once there's a broker relationship or traction to justify the cost.

---

## 3. Normalized Property Schema (draft v2)

Every record — regardless of source — resolves into one shape:

```
Property {
  id
  address: { street, city, county, zip, lat, lng }
  source: {
    type: "wholesaler_email" | "wholesaler_sms" | "public_listing" | "county_record"
    persona: "wholesaler" | "seller_agent" | "buyer_agent" | "seller" | "lender" | "builder" | "investment_partner"
    date_received
    raw_reference (original email id / message id / listing url)
  }
  listing: {
    ask_price
    status: "off_market" | "active" | "pending"
    build_year
    sqft
    lot_size
    beds / baths
  }
  condition: {
    notes (freeform, extracted)
    rehab_estimate (if provided or modeled)
    photos[] / doc_links[]
  }
  verification: {
    county_record_match: bool
    tax_history
    verified_fields[]     // which fields have been cross-checked
    unverified_fields[]   // which fields are wholesaler/agent claims only
  }
  underwriting_results: {
    fix_and_flip: {
      recommended_offer      // max price that clears the target margin, worked backward from ARV
      metric_type: "annualized_roi"
      roi_at_list
      roi_at_recommended
      margin_at_list
      margin_at_recommended
      breakdown: {...}       // ARV, rehab, selling costs, opportunity cost of cash, etc. — Angel Valley format
    } | null
    buy_and_hold: {
      recommended_offer
      metric_type: "cash_on_cash"
      coc_at_list
      coc_at_recommended
      breakdown: {...}
    } | null
    live_in_flip: {...} | null
    land_recreational: {...} | null
    str: {...} | null
  }
  offer_history: [
    { price, source: "manual" | "wholesaler_email" | "wholesaler_sms", persona, date, note }
  ]  // populated when a real negotiating price point exists — see Section 5 (negotiation scale)
  deal_reasoning: [
    {
      method: "wholesaler_conversation" | "listing_description" | "photo_analysis" | "neighborhood_analysis"
      confidence: "verified" | "likely" | "unconfirmed"
      text  // plain-language explanation of the specific opportunity mechanism
    }
  ]  // the "why this deal" layer — see Section 5a
  flags: []   // e.g. "image_only_source", "incomplete_data", "flood_zone"
}
```

Key design decisions baked in from real data (Wave Realty emails) and UI mocking:
- Must support **image-only** deals (flyer image with no usable body text) — extraction uses vision, not just text parsing.
- Must tolerate **partial records** — don't drop a deal because one field is missing; flag it instead.
- `source.type` distinguishes intake channel from day one; `source.persona` categorizes who the counterparty is without ever storing/displaying a person's actual name in generated copy.
- Every underwriting result carries **both a list-price and a recommended-offer scenario** — margin/ROI alone isn't actionable without knowing what to actually offer. `recommended_offer` is the max price that still clears the user's target return, computed backward from ARV/rent/comp value.
- `offer_history[]` is empty by default. It's populated only when a real number exists — either manually logged by the user, or extracted from an ongoing wholesaler thread (Phase 2/3). The UI never fabricates a "your offer" data point.
- `deal_reasoning[]` entries are calibrated so **confidence reflects cost-if-wrong, not just source type** — e.g. an unverified loan-assumability claim is tagged `unconfirmed` even though it reads confidently, because acting on a wrong assumption there is expensive. Structured data (county records) → `verified`. Direct interpretation of text/photos → `likely`. Secondhand/relayed claims → `unconfirmed`.

---

## 4. Underwriting Layer — Four Strategy Modules (+ STR deferred)

All modules consume the same normalized `Property` record.

| Module | Additional inputs needed | Core output |
|---|---|---|
| Fix & flip | Rehab estimate, ARV comps | Margin vs. threshold (Angel Valley model) |
| Buy & hold rental | Rent comps, financing terms | Cash-on-cash return, DSCR |
| Live-in-and-flip | Owner-occupant financing terms, 2-yr capital gains timing | Tax-adjusted return, livability score |
| Land / recreational | Zoning, utilities access, topography | Development/hold potential |

Land module needs different comp sources than standard resale/rental — flagged as a known gap to solve during Phase 2 (may require manual comp entry initially).

**STR (short-term rental) module — deferred to Phase 5.** Needs occupancy/ADR comp data (e.g. AirDNA) and a per-city/county STR legality lookup, neither sourced yet. Isolating it keeps the four core models moving without blocking on unresolved data dependencies.

---

## 5. Interface Layer

Phase 1 ships a **mobile-first ranked deal feed**, not a chat interface — the goal is zero-friction first impression: open a link on a phone, immediately see which deals are worth a look and why. Chat and full dashboard filtering come later, once there's real usage signal on what people actually want to ask. UI direction validated via HTML mock — see design notes below.

### 5a. Deal feed (Phase 1) — primary and only entry point

Mobile-responsive single page, branded **Deal Sheet**. Shows a card per deal that has cleared underwriting (i.e. the engine found real upside at some price point). No competing nav item sits alongside it — the feed is the forced first experience, not one of several equal views.

Each card surfaces:
- Address + basic facts (beds/baths, build year, or acreage for land)
- Strategy stamp (Fix & Flip, Buy & Hold, Land/Rec, etc.)
- Verification pill (county-verified vs. unverified) + matching color-coded left edge on the card
- **"Why this deal" reasoning** — one or more short callouts explaining the *specific mechanism* that makes the deal work (e.g. "rehab is cosmetic-only," "listing mentions an assumable VA loan," "seller wants a fast cash close"), each tagged with:
  - **Method**: wholesaler conversation / listing description / photo analysis / neighborhood analysis
  - **Confidence tier**: Verified (from structured records) / Likely (inferred from text or photos, not confirmed) / Unconfirmed (a claim, often secondhand — calibrated by cost-if-wrong, not just source type)
- **Negotiation scale** — a two-or-three-point price line, not a single number:
  - Always: **Recommended offer** (max price clearing target return) and **List price** (seller's ask), each with the applicable return metric (annualized ROI for finite-hold strategies like flip/land; cash-on-cash for buy & hold), explicitly labeled so the metric type is never ambiguous between cards
  - Conditionally, a **third point** — a real negotiating price (from `offer_history[]`) — appears only when actual data exists (manually logged or parsed from an ongoing thread). No placeholder or "adjustable" point is ever shown without real data behind it.
  - A "+ Log an offer" action lets the user manually add a negotiating price point (source: phone call, text, in-person, etc.) — see Phase 1 build items.
- Tap into a card ("Underwriting summary") for the full breakdown — Angel Valley–style waterfall (sale price/ARV → costs → net proceeds → total costs → gross profit → opportunity cost of cash → true net profit), ending in a cash-deployed + ROI callout.
- Deals that don't clear any strategy's threshold at any price point are simply not shown here.

After the last card, a clearly-styled (not hidden) **"Browse everything we're tracking"** button leads to All Listings. This is deliberately positioned as an earned secondary action — something reached only after engaging with the curated recommendations — not a peer-level nav tab competing with the feed.

### 5b. All Listings (Phase 1, secondary)

Reached only via the CTA at the bottom of the feed (or a "← Back to recommendations" link from within it — never a top-level tab). Shows every sourced property regardless of underwriting status, addressing the "do we need to underwrite everything" question directly:

- **No, not everything needs pre-computed underwriting.** Curated feed = deals that already cleared underwriting (cheap to fully process for wholesaler volume; a lightweight pre-screen filter for public listings avoids burning compute on every MLS-equivalent record).
- Each row in All Listings shows one of three states:
  - **"Underwritten ✓"** — already processed, tap through to the same card view
  - **"Run underwriting"** — not yet processed; user-triggered on-demand computation for a specific property the curated feed didn't surface
  - **"Incomplete — review"** — extraction failed (e.g. image-only wholesaler flyer with no usable text) and needs manual attention

**Open question carried to Phase 1 build:** should "Run underwriting" evaluate all applicable strategies for that property type automatically, or prompt the user to pick a strategy first? Affects both UI (single button vs. picker) and backend cost model.

### 5c. Later phases

- **Dashboard (Phase 4)** — full filtering, sorting, multi-strategy comparison, deal history.
- **Chat (Phase 4)** — natural-language query layer added once the feed exists and there's a sense of what people actually want to ask beyond browsing.
- **Alerts (Phase 4)** — scheduled job flagging new deals clearing threshold, via email/Slack.

---

## 6. Intake Automation — Wholesaler SMS (Phase 1 detail)

Since there's no direct API for reading native iOS texts, SMS intake is bridged via iOS Shortcuts:

1. **Dedicated Gmail address** created for SMS-sourced deals (kept separate from personal inbox).
2. **iOS Shortcut Automation**: triggers "When I receive a message" where:
   - Sender is in a maintained "Wholesalers" contact group, **OR**
   - Message body matches keywords (e.g. "deal," "off market," "wholesale," price patterns)
3. Action: auto-forward message (sender + body) as an email to the dedicated address, subject-tagged `SMS-DEAL: [sender]`.
4. The same parser built for wholesaler emails reads this inbox — no separate code path.

Known tradeoffs: keyword filter will produce false positives; contact-group filter requires manual upkeep as new wholesalers appear. Parser should tolerate noise rather than choke on it.

---

## 7. Tech Stack

Priority: free/cheap to stand up and pilot, but credible enough to share with real investors for testing from day one. Everything below upgrades in place later without re-architecting.

| Layer | Choice | Why |
|---|---|---|
| Database + backend services | **Supabase** (free tier) | Postgres + auth + file storage (for wholesaler flyer images) with near-zero infra. Built-in auth matters once multiple investors are testing with their own accounts. |
| Application/API layer | **Python + FastAPI**, hosted on **Railway** (free/hobby tier) | Python fits LLM-driven extraction and future scraping work. Railway feels closer to "always on" than Render's free tier, which sleeps on inactivity — matters for live demos. |
| Frontend | **Next.js + Tailwind**, deployed on **Vercel** (free tier) | Vercel free tier is production-grade for a pilot; instant shareable URL on every push. Use the frontend-design skill in Claude Code here so it doesn't look like a default template — first impression matters for investor testers. |
| Gmail ingestion | **Gmail API** directly | Free; same access already validated in this conversation. |
| LLM (extraction + underwriting reasoning) | **Anthropic API**, pay-as-you-go | Only real variable cost. Cheap at pilot volume (single-digit $/month expected); worth monitoring as usage grows. |
| Scheduling (email/SMS polling) | Simple cron / APScheduler, or Railway's scheduled jobs | No need for Airflow-type tooling at this scale. |

**Total cash cost to stand up + pilot: ~$0**, plus small pay-as-you-go LLM usage.

---

## 8. Phased Build Plan

**Phase 1 — Core schema + wholesaler intake (email + SMS) + one underwriting module + mobile deal feed**
- Normalized schema implementation (including `recommended_offer`, `offer_history[]`, `deal_reasoning[]`, `source.persona`)
- Gmail parser: text extraction + vision extraction for image-only deals; persona categorization (wholesaler/agent/etc.) instead of storing/surfacing personal names
- iOS Shortcut SMS-to-email bridge live
- Fix-and-flip module run end-to-end against real inbox data (e.g. the Wave Realty "Off Market Manor" deal) as proof of concept — computing both list-price and recommended-offer scenarios, not just a single margin number
- Deal-reasoning synthesis step: given structured data + unstructured notes/photos, generate "why this deal" explanations with method + confidence tagging (calibrated by cost-if-wrong)
- Manual "Log an offer" action (price, source, date) — powers the negotiation scale's third point
- **Mobile-responsive deal feed, deployed to a real Vercel URL** — branded Deal Sheet, card list of deals that clear underwriting, negotiation scale (2 or 3 points), why-this-deal reasoning, tappable Angel-Valley-style underwriting summary. Sole entry point — no competing nav.
- **All Listings view** — reached via CTA after the feed, not a top-level tab. Shows underwritten/not-yet-underwritten/incomplete status per property, with on-demand "Run underwriting" trigger.
- A deployed link is part of Phase 1's definition of done, not deferred to Phase 4.

**Phase 2 — Remaining three underwriting modules**
- Buy & hold, live-in-flip, land/recreational
- Resolve comp-data gap for land module

**Phase 3 — Public listings + county records ingestion + negotiation tracking**
- County appraisal district integration (Travis/Williamson/Hays) — structured, free, reliable
- Listings API integration (free tier first)
- Extend wholesaler parser from one-shot deal extraction to **ongoing thread monitoring** — detect price-movement signals ("would take," "countered," a new number) in follow-up messages on an already-tracked property and auto-populate `offer_history[]`, same unverified-until-confirmed treatment as other fields

**Phase 4 — Interfaces (expand beyond the feed)**
- Build full Dashboard (filters, sorting, multi-strategy comparison, deal history)
- Add Chat (natural language query layer)
- Build Alerts (scheduled threshold-based notifications)

**Phase 5 — STR module**
- Source occupancy/ADR comp data (e.g. AirDNA)
- Build STR legality lookup by city/county
- Add STR as a sixth strategy once data dependencies are resolved

**Deferred (v2):** off-market direct-seller sourcing (skip tracing, probate/tax-delinquency signals, direct outreach tooling).

---

## 9. Open Items / Decisions Still Needed

- [x] ~~Tech stack~~ — decided (see Section 7): Supabase + FastAPI/Railway + Next.js/Vercel + Anthropic API
- [ ] Which listings API to use post-free-tier (SimplyRETS vs. ATTOM vs. broker-sponsored MLS/IDX)
- [ ] Comp data source for STR module (AirDNA or equivalent) — deferred to Phase 5
- [ ] Comp data source for land/recreational module
- [ ] STR legality lookup by city/county (varies significantly across the Austin metro) — deferred to Phase 5
- [ ] "Run underwriting" scope: auto-run all applicable strategies for a property, or prompt user to pick one first? (Section 5b)
- [x] ~~RentCast field-level audit for `/listings/sale`~~ — confirmed 2026-08-27, see Section 2's "Confirmed field mapping" table. **Resolved:** photos/description are NOT available on this endpoint — RentCast-sourced deals cannot get `rehab_estimate` from listing data alone (see next item). **Still open below:** `/avm/value` and the property-records endpoint are not yet audited — only `/listings/sale` has been checked so far.
- [ ] **RentCast-sourced deals have no rehab estimate.** Confirmed gap, not hypothetical: `/listings/sale` has no photos or description text, so fix & flip's `rehab_estimate` input can't be derived the way it is for wholesaler deals. Decide: skip fix & flip underwriting for RentCast-only properties (show them in All Listings, unprocessed) vs. a rough $/sqft rehab heuristic (flagged low-confidence).
- [ ] `/avm/value` and the property-records endpoint still need their own field audit (not yet spent) — in particular whether true last-sold price/date (for `verification.tax_history`) is separate from `/listings/sale`'s `history` field (which turned out to be listing/price-change history, not confirmed closing-sale history) or from `/avm/value`'s comparables.
- [ ] Whether RentCast's property-records/sale-history lookup is a separate billable call from `/avm/value`'s comparables, or bundled — affects the per-property call cost in the Section 2 budget. Confirm during that audit.
- [x] ~~`listing.status`'s actual string values~~ — confirmed 2026-08-27: 500/500 real records mapped cleanly, see Section 2's confirmed mapping table.
- [ ] `lotSize`'s unit still isn't confirmed (assumed sqft, not verified) — `listing_lot_size_unit` is left null in the real ingested data until this is checked.
- [ ] Minor schema extension to consider before Phase 2's buy & hold module: `hoa` (present on ~50% of real listings) and MLS/agent reference fields (`mlsNumber`, etc.) exist in RentCast's response but aren't in the `Property` schema yet.
