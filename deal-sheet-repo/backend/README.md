# Deal Sheet — Backend

Property schema (spec.md Section 3) as a real Postgres database: SQLAlchemy models + Alembic migrations. This step is schema/models only — no FastAPI app, ingestion, underwriting logic, or frontend yet. See `../docs/spec.md` for the full product spec.

## Stack

SQLAlchemy 2.0 + Alembic + `psycopg` v3 + Pydantic v2. Targets Postgres — locally via Docker (or a native local install) for dev, Supabase in production. Supabase's own auth/storage/RLS aren't used here; this backend talks to Postgres directly via a standard connection string.

## Local setup

```bash
cp .env.example .env          # local defaults, no real secret in it
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d          # local Postgres 16 on localhost:5433
alembic upgrade head          # applies the schema

python scripts/seed_sample_property.py   # inserts + reads back a real sample property
```

(If Docker isn't available in your environment, any local Postgres 16 listening on `localhost:5433` with a `dealsheet`/`dealsheet` role+db works identically — `docker-compose.yml` is just the fastest path.)

## Pointing at the real Supabase database

1. In Supabase: **Connect** button (top of the project dashboard) → **Direct connection** (port 5432, *not* the transaction pooler on 6543 — Alembic's session-level DDL needs the direct connection).
2. Put that connection string in `backend/.env` (git-ignored — **never** commit real credentials, see the repo's `.gitignore`):
   ```
   DATABASE_URL=postgresql+psycopg://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require
   ```
3. `alembic upgrade head` — same migration, same result, now against the real database.

The FastAPI app (once it exists) should instead use Supabase's **transaction pooler** (port 6543) for normal request traffic — only migrations need the direct connection.

## Schema overview

- **`properties`** — the core table: address, source, listing, condition, verification (all flat columns — singular per the spec).
- **`property_underwriting_results`** — one row per `(property, strategy)`; row existence is the null/non-null signal for a strategy's result (`fix_and_flip`, `buy_and_hold`, `live_in_flip`, `land_recreational`, `str`). `result` is JSONB — see `app/schemas/underwriting.py` for the typed shapes of the two strategies the spec currently defines (`FixAndFlipResult`, `BuyAndHoldResult`); the rest are untyped placeholders until Phase 2/5.
- **`property_offers`** / **`deal_reasoning`** — append-only child tables for `offer_history[]` / `deal_reasoning[]`.
- 7 Postgres enums for the spec's closed vocabularies (`app/models/enums.py`).

## Where later pieces plug in

- Underwriting module → `app.schemas.underwriting` + inserts into `property_underwriting_results`.
- Gmail/RentCast ingestion → `properties.source_type` / `source_raw_reference` (has a partial unique index for idempotent retries).
