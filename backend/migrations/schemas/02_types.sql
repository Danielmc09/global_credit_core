-- Enum Types
-- Custom PostgreSQL enum types for the application

-- Application status lifecycle
CREATE TYPE application_status AS ENUM (
    'PENDING',
    'VALIDATING',
    'APPROVED',
    'REJECTED',
    'UNDER_REVIEW',
    'COMPLETED',
    'CANCELLED'
);

-- Supported countries
CREATE TYPE country_code AS ENUM (
    'ES',  -- España
    'PT',  -- Portugal
    'IT',  -- Italia
    'MX',  -- México
    'CO',  -- Colombia
    'BR'   -- Brasil
);

-- Webhook event processing status
CREATE TYPE webhook_event_status AS ENUM (
    'processing',
    'processed',
    'failed'
);

-- Pending job status (DB Trigger -> Queue flow)
CREATE TYPE pending_job_status AS ENUM (
    'pending',      -- Job created by trigger, waiting to be processed
    'enqueued',     -- Job picked up by worker and enqueued to ARQ
    'processing',   -- Job is being processed by ARQ worker
    'completed',    -- Job completed successfully
    'failed'        -- Job failed (moved to failed_jobs)
);
