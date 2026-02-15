"""Initial schema - all tables

Revision ID: 0001_initial
Revises: None
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create schema
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    
    # Create ENUM types
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.availability_exception_type_enum AS ENUM ('CLOSED', 'MODIFIED_HOURS', 'SPECIAL_EVENT');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.handoff_status_enum AS ENUM ('OPEN', 'ASSIGNED', 'RESOLVED', 'CLOSED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.address_type_enum AS ENUM ('PRIMARY', 'BILLING', 'BRANCH');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.booking_status_enum AS ENUM ('INITIATED', 'SLOT_SELECTED', 'CONTACT_COLLECTED', 'PAYMENT_PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED', 'HUMAN_HANDOFF', 'PENDING_PAYMENT', 'CANCELED', 'RESCHEDULED', 'EXPIRED', 'PENDING');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.resolution_type_enum AS ENUM ('AI_RESOLVED', 'HUMAN_HANDOFF', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'FAILED', 'CALL_REQUESTED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.payment_status_enum AS ENUM ('CREATED', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'REFUNDED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.conversation_channel_enum AS ENUM ('CHAT', 'VOICE', 'HUMAN');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.conversation_status_enum AS ENUM ('STARTED', 'IN_PROGRESS', 'RESOLVED', 'ABANDONED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.conversation_outcome_enum AS ENUM ('BOOKED', 'ESCALATED', 'DROPPED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.call_status_enum AS ENUM ('IN_PROGRESS', 'COMPLETED', 'ESCALATED', 'ABANDONED', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.call_resolution_enum AS ENUM ('AI_RESOLVED', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'TECHNICAL_FAILURE', 'TRANSFERRED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)
    op.execute("""
        DO SilentlyContinue BEGIN
            CREATE TYPE core.call_outcome_enum AS ENUM ('BOOKING_CREATED', 'BOOKING_CANCELLED', 'BOOKING_RESCHEDULED', 'STATUS_PROVIDED', 'INFO_PROVIDED', 'ESCALATED_TO_HUMAN', 'NO_ACTION', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN NULL; END SilentlyContinue;
    """)

    # 1. admin_users (no FK dependencies)
    op.create_table(
        "admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.String(120), nullable=True),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 2. payment_events (no FK dependencies)
    op.create_table(
        "payment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 3. businesses (FK to admin_users)
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), unique=True, nullable=False),
        sa.Column("business_name", sa.String(200), nullable=True),
        sa.Column("service_type_name", sa.String(120), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), server_default="ACTIVE", nullable=False),
        sa.Column("contact_person", sa.String(120), nullable=True),
        sa.Column("street_address", sa.Text, nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("zip_code", sa.String(30), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("default_currency", sa.String(3), server_default="BDT", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.admin_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 4. business_operating_hours
    op.create_table(
        "business_operating_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("open_time", sa.Time, nullable=True),
        sa.Column("close_time", sa.Time, nullable=True),
        sa.Column("is_closed", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 5. business_ai_settings
    op.create_table(
        "business_ai_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("agent_name", sa.String(120), server_default="AI Assistant", nullable=False),
        sa.Column("tone_of_voice", sa.String(120), nullable=True),
        sa.Column("personality", sa.Text, nullable=True),
        sa.Column("business_display_name", sa.String(200), nullable=True),
        sa.Column("is_ai_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("fallback_to_human", sa.Boolean, server_default="true", nullable=False),
        sa.Column("voice_id", sa.String(120), nullable=True),
        sa.Column("confidence_threshold", sa.Numeric(4, 3), server_default="0.650", nullable=False),
        sa.Column("allow_cancel_bookings", sa.Boolean, server_default="false", nullable=False),
        sa.Column("allow_reschedule_bookings", sa.Boolean, server_default="false", nullable=False),
        sa.Column("mention_promotions", sa.Boolean, server_default="false", nullable=False),
        sa.Column("welcome_message", sa.Text, nullable=True),
        sa.Column("fallback_message", sa.Text, nullable=True),
        sa.Column("escalation_message", sa.Text, nullable=True),
        sa.Column("max_retries", sa.Integer, nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("min_notice_hours", sa.Integer, server_default="24", nullable=False),
        sa.Column("max_per_slot", sa.Integer, server_default="1", nullable=False),
        sa.Column("cancellation_policy", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 6. business_notification_settings
    op.create_table(
        "business_notification_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("email_alerts_enabled", sa.Boolean, server_default="false", nullable=False),
        sa.Column("sms_alerts_enabled", sa.Boolean, server_default="false", nullable=False),
        sa.Column("whatsapp_alerts_enabled", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 7. business_availability_exceptions
    op.create_table(
        "business_availability_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exception_type", sa.Enum('CLOSED', 'MODIFIED_HOURS', 'SPECIAL_EVENT', name='availability_exception_type_enum', schema='core', create_type=False), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 8. business_addresses
    op.create_table(
        "business_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address_type", sa.Enum('PRIMARY', 'BILLING', 'BRANCH', name='address_type_enum', schema='core', create_type=False), server_default="PRIMARY", nullable=False),
        sa.Column("street", sa.Text, nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("zip_code", sa.String(30), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("business_id", "address_type", name="uq_business_address_type"),
        schema="core",
    )

    # 9. business_profiles
    op.create_table(
        "business_profiles",
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("contact_person", sa.String(120), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 10. services
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("service_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("timezone", sa.String(64), server_default="Asia/Dhaka", nullable=False),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("open_time", sa.Time, nullable=True),
        sa.Column("close_time", sa.Time, nullable=True),
        sa.Column("category", sa.String(50), server_default="GENERAL", nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_popular", sa.Boolean, server_default="false", nullable=False),
        sa.Column("service_type", sa.String(20), server_default="IN_PERSON", nullable=False),
        sa.Column("max_capacity", sa.Integer, server_default="1", nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 11. service_contacts
    op.create_table(
        "service_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.services.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("contact_person", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("street_address", sa.Text, nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("zip_code", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 12. service_images
    op.create_table(
        "service_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.Text, nullable=False),
        sa.Column("alt_text", sa.String(200), nullable=True),
        sa.Column("sort_order", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 13. service_capacity_rules
    op.create_table(
        "service_capacity_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.services.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("slot_length_minutes", sa.Integer, server_default="30", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 14. conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Enum('CHAT', 'VOICE', 'HUMAN', name='conversation_channel_enum', schema='core', create_type=False), nullable=False),
        sa.Column("status", sa.Enum('STARTED', 'IN_PROGRESS', 'RESOLVED', 'ABANDONED', name='conversation_status_enum', schema='core', create_type=False), server_default="STARTED", nullable=False),
        sa.Column("resolution_type", sa.Enum('AI_RESOLVED', 'HUMAN_HANDOFF', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'FAILED', 'CALL_REQUESTED', name='resolution_type_enum', schema='core', create_type=False), nullable=True),
        sa.Column("outcome", sa.Enum('BOOKED', 'ESCALATED', 'DROPPED', name='conversation_outcome_enum', schema='core', create_type=False), nullable=True),
        sa.Column("user_session_id", sa.String(120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 15. conversation_messages
    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 16. bookings
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("public_tracking_id", sa.String(20), unique=True, nullable=False),
        sa.Column("status", sa.Enum('INITIATED', 'SLOT_SELECTED', 'CONTACT_COLLECTED', 'PAYMENT_PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED', 'HUMAN_HANDOFF', 'PENDING_PAYMENT', 'CANCELED', 'RESCHEDULED', 'EXPIRED', 'PENDING', name='booking_status_enum', schema='core', create_type=False), server_default="INITIATED", nullable=False),
        sa.Column("resolution_type", sa.Enum('AI_RESOLVED', 'HUMAN_HANDOFF', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'FAILED', 'CALL_REQUESTED', name='resolution_type_enum', schema='core', create_type=False), nullable=True),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_name", sa.String(120), nullable=True),
        sa.Column("customer_phone", sa.String(40), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("contact_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("payment_status", sa.Enum('CREATED', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'REFUNDED', name='payment_status_enum', schema='core', create_type=False), server_default="CREATED", nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 17. handoff_requests
    op.create_table(
        "handoff_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Enum('OPEN', 'ASSIGNED', 'RESOLVED', 'CLOSED', name='handoff_status_enum', schema='core', create_type=False), server_default="OPEN", nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("contact_name", sa.String(120), nullable=True),
        sa.Column("contact_phone", sa.String(40), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("assigned_to_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("public_ticket_id", sa.String(24), unique=True, nullable=True),
        sa.Column("handoff_token", sa.String(80), unique=True, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 18. booking_status_history
    op.create_table(
        "booking_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.Enum('INITIATED', 'SLOT_SELECTED', 'CONTACT_COLLECTED', 'PAYMENT_PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED', 'HUMAN_HANDOFF', 'PENDING_PAYMENT', 'CANCELED', 'RESCHEDULED', 'EXPIRED', 'PENDING', name='booking_status_enum', schema='core', create_type=False), nullable=True),
        sa.Column("to_status", sa.Enum('INITIATED', 'SLOT_SELECTED', 'CONTACT_COLLECTED', 'PAYMENT_PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED', 'HUMAN_HANDOFF', 'PENDING_PAYMENT', 'CANCELED', 'RESCHEDULED', 'EXPIRED', 'PENDING', name='booking_status_enum', schema='core', create_type=False), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("changed_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 19. payment_sessions
    op.create_table(
        "payment_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_session_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), server_default="CREATED", nullable=False),
        sa.Column("payment_url", sa.Text, nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )

    # 20. call_sessions
    op.create_table(
        "call_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("public_call_id", sa.String(20), unique=True, nullable=False),
        sa.Column("provider_call_id", sa.String(100), nullable=True),
        sa.Column("caller_phone", sa.String(40), nullable=True),
        sa.Column("caller_country", sa.String(10), nullable=True),
        sa.Column("channel", sa.String(20), server_default="VOICE", nullable=False),
        sa.Column("status", sa.Enum('IN_PROGRESS', 'COMPLETED', 'ESCALATED', 'ABANDONED', 'FAILED', name='call_status_enum', schema='core', create_type=False), server_default="IN_PROGRESS", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("total_ai_messages", sa.Integer, server_default="0", nullable=False),
        sa.Column("total_user_messages", sa.Integer, server_default="0", nullable=False),
        sa.Column("resolution_type", sa.Enum('AI_RESOLVED', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'TECHNICAL_FAILURE', 'TRANSFERRED', name='call_resolution_enum', schema='core', create_type=False), nullable=True),
        sa.Column("outcome", sa.Enum('BOOKING_CREATED', 'BOOKING_CANCELLED', 'BOOKING_RESCHEDULED', 'STATUS_PROVIDED', 'INFO_PROVIDED', 'ESCALATED_TO_HUMAN', 'NO_ACTION', 'FAILED', name='call_outcome_enum', schema='core', create_type=False), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("handoff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.handoff_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("full_transcript", sa.Text, nullable=True),
        sa.Column("transcript_search", postgresql.TSVECTOR, nullable=True),
        sa.Column("extra_data", postgresql.JSONB, server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="core",
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("call_sessions", schema="core")
    op.drop_table("payment_sessions", schema="core")
    op.drop_table("booking_status_history", schema="core")
    op.drop_table("handoff_requests", schema="core")
    op.drop_table("bookings", schema="core")
    op.drop_table("conversation_messages", schema="core")
    op.drop_table("conversations", schema="core")
    op.drop_table("service_capacity_rules", schema="core")
    op.drop_table("service_images", schema="core")
    op.drop_table("service_contacts", schema="core")
    op.drop_table("services", schema="core")
    op.drop_table("business_profiles", schema="core")
    op.drop_table("business_addresses", schema="core")
    op.drop_table("business_availability_exceptions", schema="core")
    op.drop_table("business_notification_settings", schema="core")
    op.drop_table("business_ai_settings", schema="core")
    op.drop_table("business_operating_hours", schema="core")
    op.drop_table("businesses", schema="core")
    op.drop_table("payment_events", schema="core")
    op.drop_table("admin_users", schema="core")
    
    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS core.call_outcome_enum")
    op.execute("DROP TYPE IF EXISTS core.call_resolution_enum")
    op.execute("DROP TYPE IF EXISTS core.call_status_enum")
    op.execute("DROP TYPE IF EXISTS core.conversation_outcome_enum")
    op.execute("DROP TYPE IF EXISTS core.conversation_status_enum")
    op.execute("DROP TYPE IF EXISTS core.conversation_channel_enum")
    op.execute("DROP TYPE IF EXISTS core.payment_status_enum")
    op.execute("DROP TYPE IF EXISTS core.resolution_type_enum")
    op.execute("DROP TYPE IF EXISTS core.booking_status_enum")
    op.execute("DROP TYPE IF EXISTS core.address_type_enum")
    op.execute("DROP TYPE IF EXISTS core.handoff_status_enum")
    op.execute("DROP TYPE IF EXISTS core.availability_exception_type_enum")
