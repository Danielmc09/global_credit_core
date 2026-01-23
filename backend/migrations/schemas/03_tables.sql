-- Tables
-- Main application tables with proper constraints and relationships

-- Applications table
-- CRITICAL: PII fields (full_name, identity_document) are stored as encrypted BYTEA
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country country_code NOT NULL,
    full_name BYTEA NOT NULL,
    identity_document BYTEA NOT NULL,
    requested_amount DECIMAL(12, 2) NOT NULL CHECK (requested_amount > 0),
    monthly_income DECIMAL(12, 2) NOT NULL CHECK (monthly_income > 0),
    currency VARCHAR(3) NOT NULL,
    idempotency_key VARCHAR(255),
    status application_status NOT NULL DEFAULT 'PENDING',
    
    -- JSONB for extensibility
    country_specific_data JSONB DEFAULT '{}',
    banking_data JSONB DEFAULT '{}',
    
    -- Risk assessment
    risk_score DECIMAL(5, 2),
    validation_errors JSONB DEFAULT '[]',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Audit logs table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    
    -- Change tracking
    old_status application_status,
    new_status application_status NOT NULL,
    changed_by VARCHAR(100) DEFAULT 'system',
    
    -- Context
    change_reason VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Webhook events table (idempotency)
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    status webhook_event_status NOT NULL DEFAULT 'processing',
    error_message TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- Pending jobs table (DB Trigger -> Queue flow)
-- CRITICAL: Demonstrates "DB Trigger -> Job Queue" requirement
CREATE TABLE pending_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    task_name VARCHAR(255) NOT NULL DEFAULT 'process_credit_application',
    job_args JSONB DEFAULT '{}',
    job_kwargs JSONB DEFAULT '{}',
    status pending_job_status NOT NULL DEFAULT 'pending',
    arq_job_id VARCHAR(255),
    
    -- Processing timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    enqueued_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Error tracking
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Failed jobs table (Dead Letter Queue)
-- Moved after pending_jobs because it references it
CREATE TABLE failed_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pending_job_id UUID REFERENCES pending_jobs(id) ON DELETE SET NULL, -- NEW: Link to original pending job
    job_id VARCHAR(255) NOT NULL UNIQUE,
    task_name VARCHAR(255) NOT NULL,
    job_args JSONB DEFAULT '{}',
    job_kwargs JSONB DEFAULT '{}',
    
    -- Error information
    error_type VARCHAR(255) NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    
    -- Retry information
    retry_count VARCHAR(10) NOT NULL,
    max_retries VARCHAR(10) NOT NULL,
    
    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    is_retryable BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    
    -- Reprocessing
    reprocessed_at TIMESTAMP WITH TIME ZONE,
    reprocessed_job_id VARCHAR(255),
    job_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- Table comments
COMMENT ON TABLE applications IS 'Credit applications with encrypted PII';
COMMENT ON TABLE audit_logs IS 'Automatic audit trail for application status changes';
COMMENT ON TABLE webhook_events IS 'Webhook event tracking for idempotency';
COMMENT ON TABLE failed_jobs IS 'Dead Letter Queue for failed jobs';
COMMENT ON TABLE pending_jobs IS 'CRITICAL: Visible job queue created by DB triggers (Requirement 3.7)';

-- Column comments
COMMENT ON COLUMN applications.currency IS 'ISO 4217 currency code (EUR, BRL, MXN, COP). Must match country default currency.';
COMMENT ON COLUMN applications.identity_document IS 'Encrypted identity document (BYTEA) using pgcrypto. CRITICAL: PII data encrypted at rest.';
COMMENT ON COLUMN applications.full_name IS 'Encrypted full name (BYTEA) using pgcrypto. CRITICAL: PII data encrypted at rest.';
COMMENT ON COLUMN webhook_events.idempotency_key IS 'Provider reference used as idempotency key to prevent duplicate processing';
COMMENT ON COLUMN failed_jobs.status IS 'Status: pending, reviewed, reprocessed, ignored, retried';
COMMENT ON COLUMN failed_jobs.is_retryable IS 'Whether this job should be automatically retried when provider recovers (e.g., ProviderUnavailableError)';
COMMENT ON COLUMN failed_jobs.pending_job_id IS 'Reference to the original pending_job that spawned this failed job';
COMMENT ON COLUMN pending_jobs.status IS 'Job status: pending (created by trigger), enqueued (sent to ARQ), processing, completed, failed';
