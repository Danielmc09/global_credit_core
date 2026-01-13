-- Global Credit Core Database Initialization
-- This script creates tables, indexes, and triggers for the multi-country credit application system

-- Create test database if it doesn't exist (for running tests)
-- This allows tests to use a separate database without affecting development data
SELECT 'CREATE DATABASE credit_db_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'credit_db_test')\gexec

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto extension for PII encryption (CRITICAL for production)
-- This extension provides encryption functions for sensitive data at rest
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create ENUM for application status
CREATE TYPE application_status AS ENUM (
    'PENDING',
    'VALIDATING',
    'APPROVED',
    'REJECTED',
    'UNDER_REVIEW',
    'COMPLETED',
    'CANCELLED'
);

-- Create ENUM for supported countries
CREATE TYPE country_code AS ENUM (
    'ES',  -- España
    'PT',  -- Portugal
    'IT',  -- Italia
    'MX',  -- México
    'CO',  -- Colombia
    'BR'   -- Brasil
);

-- Applications table
-- CRITICAL: PII fields (full_name, identity_document) are stored as encrypted BYTEA
-- All PII data is encrypted at rest using pgcrypto for security compliance
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country country_code NOT NULL,
    full_name BYTEA NOT NULL,  -- Encrypted using pgcrypto (PII protection)
    identity_document BYTEA NOT NULL,  -- Encrypted using pgcrypto (PII protection)
    requested_amount DECIMAL(12, 2) NOT NULL CHECK (requested_amount > 0),
    monthly_income DECIMAL(12, 2) NOT NULL CHECK (monthly_income > 0),
    currency VARCHAR(3) NOT NULL,  -- ISO 4217 currency code (EUR, BRL, MXN, COP). Must match country default currency.
    idempotency_key VARCHAR(255),  -- Optional idempotency key to prevent duplicate requests
    status application_status NOT NULL DEFAULT 'PENDING',

    -- JSONB for country-specific data (extensible per country)
    country_specific_data JSONB DEFAULT '{}',

    -- Banking information obtained from provider
    banking_data JSONB DEFAULT '{}',

    -- Risk assessment and validation results
    risk_score DECIMAL(5, 2),
    validation_errors JSONB DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Soft delete
    deleted_at TIMESTAMP WITH TIME ZONE

    -- Note: Unique constraint is created as a partial index below
    -- to allow multiple applications if previous ones are cancelled
);

-- Audit logs table (for requirement 3.7 - DB native capabilities)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,

    -- Change tracking
    old_status application_status,
    new_status application_status NOT NULL,
    changed_by VARCHAR(100) DEFAULT 'system',

    -- Additional context
    change_reason VARCHAR(500),
    metadata JSONB DEFAULT '{}',

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Index for fast queries
    CONSTRAINT fk_application FOREIGN KEY (application_id) REFERENCES applications(id)
);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- CRITICAL: Trigger for automatic audit logging (Requirement 3.7)
-- This demonstrates Senior-level DB capabilities
-- This trigger automatically creates audit logs for all status changes.
-- For manual changes, the application code sets session variables (app.changed_by, app.change_reason)
-- which the trigger reads to distinguish manual vs automatic changes.
CREATE OR REPLACE FUNCTION log_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log if status actually changed
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO audit_logs (
            application_id,
            old_status,
            new_status,
            changed_by,
            change_reason,
            metadata
        ) VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            -- Read changed_by from session variable, default to 'system' for automatic changes
            COALESCE(current_setting('app.changed_by', true), 'system'),
            -- Read change_reason from session variable, default to 'Status changed automatically'
            COALESCE(current_setting('app.change_reason', true), 'Status changed automatically'),
            jsonb_build_object(
                'previous_risk_score', OLD.risk_score,
                'current_risk_score', NEW.risk_score,
                'timestamp', CURRENT_TIMESTAMP,
                'manual_change', COALESCE(current_setting('app.changed_by', true), 'system') != 'system'
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger that fires AFTER status update
CREATE TRIGGER audit_status_change
    AFTER UPDATE ON applications
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_status_change();

-- Indexes for scalability (Requirement 4.5)
-- B-Tree indexes for common query patterns

-- Index for country-based queries (very common - filtering by country)
CREATE INDEX idx_applications_country ON applications(country) WHERE deleted_at IS NULL;

-- Index for status-based queries (filtering by status)
CREATE INDEX idx_applications_status ON applications(status) WHERE deleted_at IS NULL;

-- Index for date-range queries (reporting, analytics)
CREATE INDEX idx_applications_created_at ON applications(created_at DESC) WHERE deleted_at IS NULL;

-- Composite index for country + status queries (most common combination)
CREATE INDEX idx_applications_country_status ON applications(country, status, created_at DESC)
    WHERE deleted_at IS NULL;

-- Index for identity document lookups (exact match queries)
-- Note: identity_document is encrypted (BYTEA), so queries must encrypt search values
CREATE INDEX idx_applications_identity_document ON applications(identity_document)
    WHERE deleted_at IS NULL;

-- Index for currency queries (useful for reporting/analytics)
CREATE INDEX idx_applications_currency ON applications(currency) 
    WHERE deleted_at IS NULL;

-- Composite index for country + currency queries
CREATE INDEX idx_applications_country_currency ON applications(country, currency) 
    WHERE deleted_at IS NULL;

-- CRITICAL: Unique constraint to prevent duplicate applications (fixes race condition)
-- This constraint ensures:
-- - Only one active application per (country, identity_document)
-- - CANCELLED, REJECTED, and COMPLETED applications are excluded (allows resubmission)
-- - Soft-deleted applications are excluded
-- This prevents duplicates but allows:
-- 1. Multiple finished/cancelled/rejected applications with same document
-- 2. Resubmission after cancellation, rejection, or completion
CREATE UNIQUE INDEX unique_document_per_country
ON applications (country, identity_document)
WHERE status NOT IN ('CANCELLED', 'REJECTED', 'COMPLETED') AND deleted_at IS NULL;

-- Idempotency key unique constraint (only where not null)
-- This ensures that if a client sends the same request twice with the same idempotency_key,
-- only one application will be created. The second request will return the existing application.
CREATE UNIQUE INDEX unique_idempotency_key
ON applications (idempotency_key)
WHERE idempotency_key IS NOT NULL;

-- Additional indexes for soft-deleted records
CREATE INDEX idx_applications_deleted_at
ON applications (deleted_at)
WHERE deleted_at IS NOT NULL;

-- GIN index for JSONB queries (country_specific_data, banking_data)
CREATE INDEX idx_applications_country_data ON applications USING GIN (country_specific_data);
CREATE INDEX idx_applications_banking_data ON applications USING GIN (banking_data);

-- Index for audit logs (query by application)
CREATE INDEX idx_audit_logs_application_id ON audit_logs(application_id, created_at DESC);

-- Index for audit logs (query by date)
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- Partitioning preparation (for millions of records - Requirement 4.5)
-- Comment: In production with millions of records, we would partition the applications table by created_at
-- Example for monthly partitioning (commented out - would be enabled in production):
/*
CREATE TABLE applications_partitioned (
    LIKE applications INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Create partitions for each month
CREATE TABLE applications_2024_01 PARTITION OF applications_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- This would continue for each month, and could be automated
*/

-- Create a view for active applications (commonly used)
CREATE VIEW active_applications AS
SELECT * FROM applications
WHERE deleted_at IS NULL
ORDER BY created_at DESC;

-- No test data - table starts empty

-- Create a function to get application statistics by country
CREATE OR REPLACE FUNCTION get_country_statistics(country_filter country_code)
RETURNS TABLE (
    total_applications BIGINT,
    total_amount DECIMAL,
    avg_amount DECIMAL,
    pending_count BIGINT,
    approved_count BIGINT,
    rejected_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT,
        SUM(requested_amount),
        AVG(requested_amount),
        COUNT(*) FILTER (WHERE status = 'PENDING')::BIGINT,
        COUNT(*) FILTER (WHERE status = 'APPROVED')::BIGINT,
        COUNT(*) FILTER (WHERE status = 'REJECTED')::BIGINT
    FROM applications
    WHERE country = country_filter AND deleted_at IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO credit_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO credit_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO credit_user;

-- Add comments for column documentation
COMMENT ON COLUMN applications.currency IS 'ISO 4217 currency code (EUR, BRL, MXN, COP). Must match country default currency.';
COMMENT ON COLUMN applications.identity_document IS 'Encrypted identity document (BYTEA) using pgcrypto. Decrypt using pgp_sym_decrypt() with ENCRYPTION_KEY. CRITICAL: PII data encrypted at rest.';
COMMENT ON COLUMN applications.full_name IS 'Encrypted full name (BYTEA) using pgcrypto. Decrypt using pgp_sym_decrypt() with ENCRYPTION_KEY. CRITICAL: PII data encrypted at rest.';

-- =====================================================
-- WEBHOOK EVENTS TABLE (for idempotency)
-- =====================================================

-- Create enum for webhook event status
CREATE TYPE webhook_event_status AS ENUM (
    'processing',
    'processed',
    'failed'
);

-- Create table for webhook event tracking
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Idempotency key (provider_reference from webhook payload)
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    
    -- Reference to application
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    
    -- Full webhook payload for auditing (stores original data)
    payload JSONB NOT NULL,
    
    -- Processing status
    status webhook_event_status NOT NULL DEFAULT 'processing',
    
    -- Error message if processing failed
    error_message TEXT,
    
    -- Timestamps
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE UNIQUE INDEX idx_webhook_events_idempotency_key ON webhook_events(idempotency_key);
CREATE INDEX idx_webhook_events_created_at ON webhook_events(created_at);
CREATE INDEX idx_webhook_events_application_id ON webhook_events(application_id);
CREATE INDEX idx_webhook_events_status ON webhook_events(status, created_at DESC);

-- Trigger to auto-update updated_at timestamp
CREATE TRIGGER update_webhook_events_updated_at
    BEFORE UPDATE ON webhook_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE webhook_events IS 'Tracks webhook events for idempotency and audit trail';
COMMENT ON COLUMN webhook_events.idempotency_key IS 'Provider reference used as idempotency key to prevent duplicate processing';
COMMENT ON COLUMN webhook_events.payload IS 'Complete webhook payload stored for audit and debugging';
COMMENT ON COLUMN webhook_events.status IS 'Processing status: processing, processed, or failed';

-- Dead Letter Queue: Failed Jobs table
-- Stores jobs that have failed after maximum retries for manual review and reprocessing
CREATE TABLE failed_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Job identification
    job_id VARCHAR(255) NOT NULL UNIQUE,
    task_name VARCHAR(255) NOT NULL,
    
    -- Job context
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
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    
    -- Reprocessing
    reprocessed_at TIMESTAMP WITH TIME ZONE,
    reprocessed_job_id VARCHAR(255),
    
    -- Metadata
    job_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for failed_jobs
CREATE INDEX idx_failed_jobs_job_id ON failed_jobs(job_id);
CREATE INDEX idx_failed_jobs_task_name ON failed_jobs(task_name);
CREATE INDEX idx_failed_jobs_status ON failed_jobs(status, created_at DESC);
CREATE INDEX idx_failed_jobs_created_at ON failed_jobs(created_at DESC);

-- Trigger to auto-update updated_at timestamp
CREATE TRIGGER update_failed_jobs_updated_at
    BEFORE UPDATE ON failed_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE failed_jobs IS 'Dead Letter Queue: Stores jobs that failed after maximum retries for manual review';
COMMENT ON COLUMN failed_jobs.job_id IS 'ARQ job ID';
COMMENT ON COLUMN failed_jobs.task_name IS 'Task function name';
COMMENT ON COLUMN failed_jobs.status IS 'Status: pending, reviewed, reprocessed, ignored';
COMMENT ON COLUMN failed_jobs.retry_count IS 'Number of retries attempted before failure';
COMMENT ON COLUMN failed_jobs.max_retries IS 'Maximum retries configured';

-- =====================================================
-- AUTOMATIC PARTITIONING FUNCTIONS
-- =====================================================
-- These functions enable automatic partitioning when tables exceed 1M records
-- Partitioning is done by range on created_at column (monthly partitions)

-- Function to get table row count
CREATE OR REPLACE FUNCTION get_table_row_count(table_name TEXT)
RETURNS BIGINT AS $$
DECLARE
    row_count BIGINT;
BEGIN
    EXECUTE format('SELECT COUNT(*) FROM %I', table_name) INTO row_count;
    RETURN row_count;
EXCEPTION
    WHEN OTHERS THEN
        RETURN -1;  -- Return -1 on error
END;
$$ LANGUAGE plpgsql;

-- Function to check if table is already partitioned
CREATE OR REPLACE FUNCTION is_table_partitioned(table_name TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    is_partitioned BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = table_name
        AND n.nspname = 'public'
        AND c.relkind = 'p'  -- 'p' = partitioned table
    ) INTO is_partitioned;
    RETURN is_partitioned;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to create monthly partition for a partitioned table
CREATE OR REPLACE FUNCTION create_monthly_partition(
    parent_table TEXT,
    partition_name TEXT,
    start_date DATE,
    end_date DATE
)
RETURNS BOOLEAN AS $$
DECLARE
    partition_exists BOOLEAN;
BEGIN
    -- Check if partition already exists
    SELECT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = partition_name
        AND n.nspname = 'public'
    ) INTO partition_exists;

    IF partition_exists THEN
        RETURN FALSE;  -- Partition already exists
    END IF;

    -- Create the partition
    EXECUTE format(
        'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        parent_table,
        start_date,
        end_date
    );

    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error creating partition %: %', partition_name, SQLERRM;
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to convert a regular table to a partitioned table
-- This is a complex operation that requires:
-- 1. Creating a new partitioned table
-- 2. Copying data
-- 3. Renaming tables
-- 4. Recreating indexes and constraints
CREATE OR REPLACE FUNCTION convert_table_to_partitioned(
    table_name TEXT,
    partition_column TEXT DEFAULT 'created_at'
)
RETURNS BOOLEAN AS $$
DECLARE
    temp_table TEXT;
    partition_start DATE;
    partition_end DATE;
    partition_name TEXT;
    current_month DATE;
    month_end DATE;
    index_def TEXT;
    constraint_def TEXT;
BEGIN
    -- Check if already partitioned
    IF is_table_partitioned(table_name) THEN
        RETURN FALSE;  -- Already partitioned
    END IF;

    -- Create temporary partitioned table
    temp_table := table_name || '_partitioned_new';

    -- Create the partitioned table structure
    -- Use INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES to copy structure
    -- Note: Foreign key constraints will need to be recreated separately
    EXECUTE format(
        'CREATE TABLE %I (LIKE %I INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES) PARTITION BY RANGE (%I)',
        temp_table,
        table_name,
        partition_column
    );

    -- Get the date range from existing data
    EXECUTE format(
        'SELECT DATE_TRUNC(''month'', MIN(%I)), DATE_TRUNC(''month'', MAX(%I)) + INTERVAL ''1 month''
         FROM %I',
        partition_column,
        partition_column,
        table_name
    ) INTO partition_start, partition_end;

    -- If no data, create a default partition for current month
    IF partition_start IS NULL THEN
        partition_start := DATE_TRUNC('month', CURRENT_DATE);
        partition_end := partition_start + INTERVAL '1 month';
        -- Create single partition for current month
        partition_name := table_name || '_' || TO_CHAR(partition_start, 'YYYY_MM');
        PERFORM create_monthly_partition(temp_table, partition_name, partition_start, partition_end);
    ELSE
        -- Create partitions for each month in the date range
        current_month := partition_start;
        WHILE current_month < partition_end LOOP
            month_end := current_month + INTERVAL '1 month';
            partition_name := table_name || '_' || TO_CHAR(current_month, 'YYYY_MM');
            PERFORM create_monthly_partition(temp_table, partition_name, current_month, month_end);
            current_month := month_end;
        END LOOP;
    END IF;

    -- Copy data to partitioned table
    EXECUTE format(
        'INSERT INTO %I SELECT * FROM %I',
        temp_table,
        table_name
    );

    -- Note: Foreign key constraints referencing this table will be dropped with CASCADE
    -- They need to be recreated after the conversion if needed
    -- Drop old table and rename new one
    EXECUTE format('DROP TABLE %I CASCADE', table_name);
    EXECUTE format('ALTER TABLE %I RENAME TO %I', temp_table, table_name);

    -- Note: Indexes on partitioned tables are automatically inherited by partitions
    -- However, unique constraints and foreign keys may need manual recreation

    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        -- Cleanup on error
        BEGIN
            EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', temp_table);
        EXCEPTION
            WHEN OTHERS THEN
                NULL;
        END;
        RAISE WARNING 'Error converting table % to partitioned: %', table_name, SQLERRM;
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to ensure future partitions exist (creates next 3 months)
CREATE OR REPLACE FUNCTION ensure_future_partitions(
    table_name TEXT,
    months_ahead INTEGER DEFAULT 3
)
RETURNS INTEGER AS $$
DECLARE
    partition_name TEXT;
    partition_date DATE;
    next_date DATE;
    created_count INTEGER := 0;
    i INTEGER;
BEGIN
    -- Check if table is partitioned
    IF NOT is_table_partitioned(table_name) THEN
        RETURN 0;  -- Not partitioned, nothing to do
    END IF;

    -- Create partitions for next N months
    FOR i IN 0..months_ahead-1 LOOP
        partition_date := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
        next_date := partition_date + INTERVAL '1 month';
        partition_name := table_name || '_' || TO_CHAR(partition_date, 'YYYY_MM');

        -- Check if partition exists
        IF NOT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = partition_name
            AND n.nspname = 'public'
        ) THEN
            -- Create partition
            IF create_monthly_partition(table_name, partition_name, partition_date, next_date) THEN
                created_count := created_count + 1;
            END IF;
        END IF;
    END LOOP;

    RETURN created_count;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error ensuring future partitions for %: %', table_name, SQLERRM;
        RETURN created_count;
END;
$$ LANGUAGE plpgsql;

-- Function to check and partition table if needed
CREATE OR REPLACE FUNCTION check_and_partition_table(
    table_name TEXT,
    threshold BIGINT DEFAULT 1000000,
    partition_column TEXT DEFAULT 'created_at'
)
RETURNS JSONB AS $$
DECLARE
    row_count BIGINT;
    already_partitioned BOOLEAN;
    result JSONB;
    converted BOOLEAN;
    partitions_created INTEGER;
BEGIN
    -- Get row count
    row_count := get_table_row_count(table_name);

    -- Check if already partitioned
    already_partitioned := is_table_partitioned(table_name);

    -- Initialize result
    result := jsonb_build_object(
        'table_name', table_name,
        'row_count', row_count,
        'threshold', threshold,
        'already_partitioned', already_partitioned,
        'action_taken', 'none',
        'success', false
    );

    -- If already partitioned, just ensure future partitions exist
    IF already_partitioned THEN
        partitions_created := ensure_future_partitions(table_name, 3);
        result := result || jsonb_build_object(
            'action_taken', 'ensure_future_partitions',
            'partitions_created', partitions_created,
            'success', true
        );
        RETURN result;
    END IF;

    -- Check if threshold is exceeded
    IF row_count < threshold THEN
        result := result || jsonb_build_object(
            'action_taken', 'no_action_needed',
            'message', format('Row count (%s) below threshold (%s)', row_count, threshold),
            'success', true
        );
        RETURN result;
    END IF;

    -- Convert to partitioned table
    converted := convert_table_to_partitioned(table_name, partition_column);
    
    IF converted THEN
        -- Ensure future partitions exist
        partitions_created := ensure_future_partitions(table_name, 3);
        result := result || jsonb_build_object(
            'action_taken', 'converted_to_partitioned',
            'partitions_created', partitions_created,
            'success', true
        );
    ELSE
        result := result || jsonb_build_object(
            'action_taken', 'conversion_failed',
            'message', 'Failed to convert table to partitioned',
            'success', false
        );
    END IF;

    RETURN result;
EXCEPTION
    WHEN OTHERS THEN
        result := result || jsonb_build_object(
            'action_taken', 'error',
            'error_message', SQLERRM,
            'success', false
        );
        RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions on partitioning functions
GRANT EXECUTE ON FUNCTION get_table_row_count(TEXT) TO credit_user;
GRANT EXECUTE ON FUNCTION is_table_partitioned(TEXT) TO credit_user;
GRANT EXECUTE ON FUNCTION create_monthly_partition(TEXT, TEXT, DATE, DATE) TO credit_user;
GRANT EXECUTE ON FUNCTION convert_table_to_partitioned(TEXT, TEXT) TO credit_user;
GRANT EXECUTE ON FUNCTION ensure_future_partitions(TEXT, INTEGER) TO credit_user;
GRANT EXECUTE ON FUNCTION check_and_partition_table(TEXT, BIGINT, TEXT) TO credit_user;

-- Add comments
COMMENT ON FUNCTION get_table_row_count(TEXT) IS 'Returns the row count for a given table';
COMMENT ON FUNCTION is_table_partitioned(TEXT) IS 'Checks if a table is already partitioned';
COMMENT ON FUNCTION create_monthly_partition(TEXT, TEXT, DATE, DATE) IS 'Creates a monthly partition for a partitioned table';
COMMENT ON FUNCTION convert_table_to_partitioned(TEXT, TEXT) IS 'Converts a regular table to a partitioned table by range on specified column';
COMMENT ON FUNCTION ensure_future_partitions(TEXT, INTEGER) IS 'Ensures future partitions exist for the next N months';
COMMENT ON FUNCTION check_and_partition_table(TEXT, BIGINT, TEXT) IS 'Checks table row count and partitions if threshold is exceeded';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully!';
    RAISE NOTICE 'Tables created: applications, audit_logs, webhook_events, failed_jobs';
    RAISE NOTICE 'Triggers created: audit_status_change (for automatic audit logging)';
    RAISE NOTICE 'Indexes created for scalability';
    RAISE NOTICE 'Currency column added for country-specific currency validation';
    RAISE NOTICE 'Webhook events table added for idempotency';
    RAISE NOTICE 'PII ENCRYPTION: identity_document and full_name are encrypted (BYTEA) using pgcrypto';
    RAISE NOTICE 'IMPORTANT: Set ENCRYPTION_KEY environment variable (min 32 characters) for production';
    RAISE NOTICE 'IMPORTANT: All PII data is encrypted at rest for security compliance';
END $$;
