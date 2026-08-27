# Deal Sheet

Underwriting assistant for Austin real estate investors — sources deals from MLS-equivalent listings, county records, and inbound wholesaler emails/texts, then runs each one through investor-specific underwriting (fix & flip, buy & hold, live-in-and-flip, land/recreational, with STR planned later).

## What's in this repo

- **[`docs/spec.md`](docs/spec.md)** — full product & technical spec: scope, sourcing strategy, normalized schema, underwriting modules, tech stack, phased build plan, and open decisions.
- **[`design/deal-feed-mock.html`](design/deal-feed-mock.html)** — mobile-first HTML mock of the Phase 1 deal feed. Open directly in a browser (or on your phone) to see the actual UI: negotiation scale, "why this deal" reasoning with confidence tiers, and the All Listings view.

## Status

Phase 1 scoping complete, UI design validated via mock. Not yet built.

## Current phase plan

1. Core schema + wholesaler intake (email + SMS) + fix & flip module + mobile deal feed
2. Remaining underwriting modules (buy & hold, live-in-flip, land/recreational)
3. Public listings + county records ingestion + negotiation tracking
4. Full interfaces (dashboard, chat, alerts)
5. STR module

See `docs/spec.md` Section 8 for full detail.
