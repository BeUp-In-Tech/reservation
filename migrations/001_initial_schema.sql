-- ============================================================
-- AI BOOKING SYSTEM - COMPLETE DATABASE MIGRATION
-- Version: 1.0.0
-- Run: psql -U postgres -d your_database -f migrations/001_initial_schema.sql
-- ============================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS core;

-- ============================================================
-- TABLE: admin_users
-- ============================================================

CREATE TABLE IF NOT EXISTS core.admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(120),
    role VARCHAR(40) NOT NULL DEFAULT 'ADMIN',
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: businesses
-- ============================================================

CREATE TABLE IF NOT EXISTS core.businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(140) UNIQUE NOT NULL,
    business_name VARCHAR(200) NOT NULL,
    industry VARCHAR(50) DEFAULT 'OTHER',
    industry_label VARCHAR(100),
    timezone VARCHAR(60) DEFAULT 'UTC',
    status VARCHAR(30) DEFAULT 'ACTIVE',
    description TEXT,
    phone VARCHAR(40),
    email VARCHAR(255),
    website VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    default_currency VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    created_by_admin_id UUID REFERENCES core.admin_users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: business_operating_hours
-- ============================================================

CREATE TABLE IF NOT EXISTS core.business_operating_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6),
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(business_id, day_of_week)
);

-- ============================================================
-- TABLE: business_ai_settings
-- ============================================================

CREATE TABLE IF NOT EXISTS core.business_ai_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID UNIQUE NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    agent_name VARCHAR(120) NOT NULL DEFAULT 'Assistant',
    tone_of_voice VARCHAR(120) DEFAULT 'friendly and professional',
    personality TEXT,
    business_display_name VARCHAR(200),
    is_ai_enabled BOOLEAN DEFAULT TRUE,
    fallback_to_human BOOLEAN DEFAULT TRUE,
    voice_id VARCHAR(120),
    confidence_threshold NUMERIC(4,3) DEFAULT 0.650,
    allow_cancel_bookings BOOLEAN DEFAULT FALSE,
    allow_reschedule_bookings BOOLEAN DEFAULT FALSE,
    mention_promotions BOOLEAN DEFAULT FALSE,
    welcome_message TEXT DEFAULT 'Hello! How can I help you today?',
    fallback_message TEXT DEFAULT 'I''m sorry, I didn''t understand that.',
    escalation_message TEXT DEFAULT 'I''ll connect you with a human representative.',
    max_retries INTEGER DEFAULT 3,
    language VARCHAR(10) DEFAULT 'en',
    min_notice_hours INTEGER DEFAULT 24,
    max_per_slot INTEGER DEFAULT 1,
    cancellation_policy TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: business_notification_settings
-- ============================================================

CREATE TABLE IF NOT EXISTS core.business_notification_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID UNIQUE NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    email_alerts_enabled BOOLEAN DEFAULT FALSE,
    sms_alerts_enabled BOOLEAN DEFAULT FALSE,
    whatsapp_alerts_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: business_availability_exceptions
-- ============================================================

CREATE TABLE IF NOT EXISTS core.business_availability_exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    exception_type VARCHAR(30) NOT NULL,
    start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    end_at TIMESTAMP WITH TIME ZONE NOT NULL,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: services
-- ============================================================

CREATE TABLE IF NOT EXISTS core.services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    slug VARCHAR(140) NOT NULL,
    service_name VARCHAR(200) NOT NULL,
    description TEXT,
    base_price NUMERIC(12,2),
    currency VARCHAR(3) DEFAULT 'USD',
    duration_minutes INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    category VARCHAR(50) DEFAULT 'GENERAL',
    location VARCHAR(200),
    is_popular BOOLEAN DEFAULT FALSE,
    service_type VARCHAR(20) DEFAULT 'IN_PERSON',
    max_capacity INTEGER DEFAULT 1,
    icon VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(business_id, slug)
);

-- ============================================================
-- TABLE: service_images
-- ============================================================

CREATE TABLE IF NOT EXISTS core.service_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    service_id UUID NOT NULL REFERENCES core.services(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    alt_text VARCHAR(200),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: service_capacity_rules
-- ============================================================

CREATE TABLE IF NOT EXISTS core.service_capacity_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    service_id UUID UNIQUE NOT NULL REFERENCES core.services(id) ON DELETE CASCADE,
    capacity INTEGER NOT NULL DEFAULT 1,
    slot_length_minutes INTEGER DEFAULT 30,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: conversations
-- ============================================================

CREATE TABLE IF NOT EXISTS core.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    channel VARCHAR(20) DEFAULT 'CHAT',
    status VARCHAR(30) DEFAULT 'STARTED',
    user_session_id VARCHAR(255),
    resolution_type VARCHAR(30),
    outcome TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: conversation_messages
-- ============================================================

CREATE TABLE IF NOT EXISTS core.conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES core.conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id ON core.conversation_messages(conversation_id);

-- ============================================================
-- TABLE: bookings
-- ============================================================

CREATE TABLE IF NOT EXISTS core.bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    service_id UUID REFERENCES core.services(id),
    conversation_id UUID REFERENCES core.conversations(id),
    public_tracking_id VARCHAR(24) UNIQUE NOT NULL,
    status VARCHAR(30) DEFAULT 'INITIATED',
    slot_start TIMESTAMP WITH TIME ZONE,
    slot_end TIMESTAMP WITH TIME ZONE,
    customer_name VARCHAR(120),
    customer_phone VARCHAR(40),
    customer_email VARCHAR(255),
    customer_notes TEXT,
    internal_notes TEXT,
    payment_status VARCHAR(30) DEFAULT 'PENDING',
    payment_amount NUMERIC(12,2),
    payment_currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bookings_business_id ON core.bookings(business_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON core.bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_public_tracking_id ON core.bookings(public_tracking_id);

-- ============================================================
-- TABLE: booking_status_history
-- ============================================================

CREATE TABLE IF NOT EXISTS core.booking_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES core.bookings(id) ON DELETE CASCADE,
    old_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    changed_by_admin_id UUID REFERENCES core.admin_users(id),
    change_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: call_sessions
-- ============================================================

CREATE TABLE IF NOT EXISTS core.call_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES core.conversations(id),
    handoff_id UUID,
    public_call_id VARCHAR(24) UNIQUE NOT NULL,
    provider_call_id VARCHAR(255),
    caller_phone VARCHAR(40),
    channel VARCHAR(20) DEFAULT 'VOICE',
    status VARCHAR(30) DEFAULT 'IN_PROGRESS',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    transcript TEXT,
    recording_url TEXT,
    resolution_type VARCHAR(30),
    outcome TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: handoff_requests
-- ============================================================

CREATE TABLE IF NOT EXISTS core.handoff_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES core.conversations(id),
    booking_id UUID REFERENCES core.bookings(id),
    status VARCHAR(30) DEFAULT 'OPEN',
    reason VARCHAR(80) NOT NULL,
    contact_name VARCHAR(120),
    contact_phone VARCHAR(40),
    contact_email VARCHAR(255),
    assigned_to_admin_id UUID REFERENCES core.admin_users(id),
    public_ticket_id VARCHAR(24) UNIQUE,
    handoff_token VARCHAR(80) UNIQUE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add FK for call_sessions.handoff_id
ALTER TABLE core.call_sessions 
    DROP CONSTRAINT IF EXISTS fk_call_sessions_handoff_id;
ALTER TABLE core.call_sessions 
    ADD CONSTRAINT fk_call_sessions_handoff_id 
    FOREIGN KEY (handoff_id) REFERENCES core.handoff_requests(id);

-- ============================================================
-- TABLE: payment_sessions
-- ============================================================

CREATE TABLE IF NOT EXISTS core.payment_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    booking_id UUID NOT NULL REFERENCES core.bookings(id) ON DELETE CASCADE,
    provider VARCHAR(30) NOT NULL,
    provider_session_id VARCHAR(255),
    amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(30) DEFAULT 'CREATED',
    payment_url TEXT,
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: payment_events
-- ============================================================

CREATE TABLE IF NOT EXISTS core.payment_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL,
    provider VARCHAR(30) NOT NULL,
    provider_event_id VARCHAR(255),
    event_type VARCHAR(120) NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: system_events
-- ============================================================

CREATE TABLE IF NOT EXISTS core.system_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- TABLE: admin_business_access
-- ============================================================

CREATE TABLE IF NOT EXISTS core.admin_business_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID NOT NULL REFERENCES core.admin_users(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES core.businesses(id) ON DELETE CASCADE,
    access_level VARCHAR(30) DEFAULT 'FULL',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(admin_id, business_id)
);

-- ============================================================
-- INSERT DEFAULT ADMIN (email: admin@yourdomain.com, password: admin123)
-- ============================================================

INSERT INTO core.admin_users (email, password_hash, full_name, role, is_active)
VALUES (
    'admin@yourdomain.com',
    '\\\/X4.VTtYE3i9FGKXaS',
    'System Admin',
    'ADMIN',
    TRUE
)
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- SAMPLE DATA: Demo Business
-- ============================================================

INSERT INTO core.businesses (id, slug, business_name, industry, timezone, default_currency, is_active)
VALUES (
    'bfa73499-59af-41c4-a17a-8b739453f99a',
    'demo-business',
    'Demo Business',
    'OTHER',
    'UTC',
    'USD',
    TRUE
)
ON CONFLICT (slug) DO NOTHING;

-- AI Settings for demo business
INSERT INTO core.business_ai_settings (business_id, agent_name, tone_of_voice, welcome_message)
VALUES (
    'bfa73499-59af-41c4-a17a-8b739453f99a',
    'Alex',
    'friendly and professional',
    'Hello! Welcome to Demo Business. How can I help you today?'
)
ON CONFLICT (business_id) DO NOTHING;

-- Sample service
INSERT INTO core.services (business_id, slug, service_name, description, base_price, currency, duration_minutes, is_active)
VALUES (
    'bfa73499-59af-41c4-a17a-8b739453f99a',
    'consultation',
    'Consultation',
    'One-on-one consultation session',
    50.00,
    'USD',
    60,
    TRUE
)
ON CONFLICT (business_id, slug) DO NOTHING;

-- Operating hours (Mon-Fri 9am-6pm)
INSERT INTO core.business_operating_hours (business_id, day_of_week, open_time, close_time, is_closed)
SELECT 
    'bfa73499-59af-41c4-a17a-8b739453f99a',
    d,
    '09:00:00'::TIME,
    '18:00:00'::TIME,
    CASE WHEN d IN (5, 6) THEN TRUE ELSE FALSE END
FROM generate_series(0, 6) AS d
ON CONFLICT (business_id, day_of_week) DO NOTHING;

-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================

SELECT 'Database migration completed successfully!' AS status;
SELECT COUNT(*) AS admin_count FROM core.admin_users;
SELECT COUNT(*) AS business_count FROM core.businesses;
SELECT COUNT(*) AS service_count FROM core.services;
