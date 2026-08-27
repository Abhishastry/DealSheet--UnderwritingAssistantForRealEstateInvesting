"""initial property schema

Revision ID: 44ce8a40ba59
Revises:
Create Date: 2026-08-27 04:28:31.400421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '44ce8a40ba59'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- Postgres ENUM types (spec.md Section 3's closed vocabularies) ---
# Defined explicitly here, once, and created/dropped by hand below rather than
# relying on op.create_table's implicit checkfirst-create behavior — autogenerate
# doesn't reliably manage native enum lifecycle, so this migration owns it directly.
# create_type=False on every column usage below: these CREATE/DROP calls are the
# only thing allowed to create or drop the type itself.
source_type_enum = postgresql.ENUM(
    'wholesaler_email', 'wholesaler_sms', 'public_listing', 'county_record',
    name='source_type', create_type=False,
)
persona_enum = postgresql.ENUM(
    'wholesaler', 'seller_agent', 'buyer_agent', 'seller', 'lender', 'builder', 'investment_partner',
    name='persona', create_type=False,
)
listing_status_enum = postgresql.ENUM('off_market', 'active', 'pending', name='listing_status', create_type=False)
lot_size_unit_enum = postgresql.ENUM('sqft', 'acres', name='lot_size_unit', create_type=False)
deal_reasoning_method_enum = postgresql.ENUM(
    'wholesaler_conversation', 'listing_description', 'photo_analysis', 'neighborhood_analysis',
    name='deal_reasoning_method', create_type=False,
)
deal_reasoning_confidence_enum = postgresql.ENUM(
    'verified', 'likely', 'unconfirmed', name='deal_reasoning_confidence', create_type=False,
)
offer_source_enum = postgresql.ENUM(
    'manual', 'wholesaler_email', 'wholesaler_sms', name='offer_source', create_type=False,
)
underwriting_strategy_enum = postgresql.ENUM(
    'fix_and_flip', 'buy_and_hold', 'live_in_flip', 'land_recreational', 'str',
    name='underwriting_strategy', create_type=False,
)

_ALL_ENUMS = [
    source_type_enum,
    persona_enum,
    listing_status_enum,
    lot_size_unit_enum,
    deal_reasoning_method_enum,
    deal_reasoning_confidence_enum,
    offer_source_enum,
    underwriting_strategy_enum,
]


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    for enum_type in _ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table('properties',
    sa.Column('address_street', sa.String(length=255), nullable=False),
    sa.Column('address_city', sa.String(length=120), nullable=False),
    sa.Column('address_county', sa.String(length=120), nullable=True),
    sa.Column('address_zip', sa.String(length=10), nullable=False),
    sa.Column('address_lat', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('address_lng', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('source_type', source_type_enum, nullable=False),
    sa.Column('source_persona', persona_enum, nullable=False),
    sa.Column('source_date_received', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('source_raw_reference', sa.Text(), nullable=True),
    sa.Column('listing_ask_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('listing_status', listing_status_enum, nullable=True),
    sa.Column('listing_build_year', sa.SmallInteger(), nullable=True),
    sa.Column('listing_sqft', sa.Integer(), nullable=True),
    sa.Column('listing_lot_size', sa.Numeric(precision=10, scale=3), nullable=True),
    sa.Column('listing_lot_size_unit', lot_size_unit_enum, nullable=True),
    sa.Column('listing_beds', sa.SmallInteger(), nullable=True),
    sa.Column('listing_baths', sa.Numeric(precision=3, scale=1), nullable=True),
    sa.Column('condition_notes', sa.Text(), nullable=True),
    sa.Column('condition_rehab_estimate', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('condition_photos', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('condition_doc_links', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('verification_county_record_match', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('verification_tax_history', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('verification_verified_fields', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('verification_unverified_fields', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('underwriting_cleared', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('flags', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_properties_address_zip', 'properties', ['address_zip'], unique=False)
    op.create_index('ix_properties_flags_gin', 'properties', ['flags'], unique=False, postgresql_using='gin')
    op.create_index('ix_properties_source_type', 'properties', ['source_type'], unique=False)
    op.create_index('ix_properties_source_type_raw_reference_unique', 'properties', ['source_type', 'source_raw_reference'], unique=True, postgresql_where=sa.text('source_raw_reference IS NOT NULL'))
    op.create_index('ix_properties_underwriting_cleared', 'properties', ['underwriting_cleared'], unique=False)
    op.create_table('deal_reasoning',
    sa.Column('property_id', sa.UUID(), nullable=False),
    sa.Column('method', deal_reasoning_method_enum, nullable=False),
    sa.Column('confidence', deal_reasoning_confidence_enum, nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('sort_order', sa.SmallInteger(), server_default='0', nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deal_reasoning_property_id'), 'deal_reasoning', ['property_id'], unique=False)
    op.create_table('property_offers',
    sa.Column('property_id', sa.UUID(), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('source', offer_source_enum, nullable=False),
    sa.Column('persona', persona_enum, nullable=True),
    sa.Column('occurred_at', sa.Date(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_property_offers_property_id'), 'property_offers', ['property_id'], unique=False)
    op.create_table('property_underwriting_results',
    sa.Column('property_id', sa.UUID(), nullable=False),
    sa.Column('strategy', underwriting_strategy_enum, nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('computed_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('model_version', sa.String(length=50), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('property_id', 'strategy', name='uq_property_underwriting_strategy')
    )
    op.create_index(op.f('ix_property_underwriting_results_property_id'), 'property_underwriting_results', ['property_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_property_underwriting_results_property_id'), table_name='property_underwriting_results')
    op.drop_table('property_underwriting_results')
    op.drop_index(op.f('ix_property_offers_property_id'), table_name='property_offers')
    op.drop_table('property_offers')
    op.drop_index(op.f('ix_deal_reasoning_property_id'), table_name='deal_reasoning')
    op.drop_table('deal_reasoning')
    op.drop_index('ix_properties_underwriting_cleared', table_name='properties')
    op.drop_index('ix_properties_source_type_raw_reference_unique', table_name='properties', postgresql_where=sa.text('source_raw_reference IS NOT NULL'))
    op.drop_index('ix_properties_source_type', table_name='properties')
    op.drop_index('ix_properties_flags_gin', table_name='properties', postgresql_using='gin')
    op.drop_index('ix_properties_address_zip', table_name='properties')
    op.drop_table('properties')

    bind = op.get_bind()
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)
