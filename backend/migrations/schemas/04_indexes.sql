-- Indexes
-- Performance indexes for common query patterns

-- =====================================================
-- APPLICATIONS TABLE INDEXES
-- =====================================================

-- Country-based queries (very common)
CREATE INDEX idx_applications_country ON applications(country) WHERE deleted_at IS NULL;

-- Status-based queries
CREATE INDEX idx_applications_status ON applications(status) WHERE deleted_at IS NULL;

-- Date-range queries (reporting, analytics)
CREATE INDEX idx_applications_created_at ON applications(created_at DESC) WHERE deleted_at IS NULL;

-- Composite index for country + status (most common combination)
CREATE INDEX idx_applications_country_status ON applications(country, status, created_at DESC)
    WHERE deleted_at IS NULL;

-- Identity document lookups (encrypted BYTEA)
CREATE INDEX idx_applications_identity_document ON applications(identity_document)
    WHERE deleted_at IS NULL;

-- Currency queries
CREATE INDEX idx_applications_currency ON applications(currency) 
    WHERE deleted_at IS NULL;

-- Composite index for country + currency
CREATE INDEX idx_applications_country_currency ON applications(country, currency) 
    WHERE deleted_at IS NULL;

-- Soft-deleted records
CREATE INDEX idx_applications_deleted_at ON applications(deleted_at)
    WHERE deleted_at IS NOT NULL;

-- GIN indexes for JSONB queries
CREATE INDEX idx_applications_country_data ON applications USING GIN (country_specific_data);
CREATE INDEX idx_applications_banking_data ON applications USING GIN (banking_data);

-- CRITICAL: Unique constraints
-- Prevent duplicate active applications (allows resubmission after cancellation/rejection)
CREATE UNIQUE INDEX unique_document_per_country
ON applications (country, identity_document)
WHERE status NOT IN ('CANCELLED', 'REJECTED', 'COMPLETED') AND deleted_at IS NULL;

-- Idempotency key unique constraint
CREATE UNIQUE INDEX unique_idempotency_key
ON applications (idempotency_key)
WHERE idempotency_key IS NOT NULL;

-- =====================================================
-- AUDIT LOGS INDEXES
-- =====================================================

CREATE INDEX idx_audit_logs_application_id ON audit_logs(application_id, created_at DESC);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- =====================================================
-- WEBHOOK EVENTS INDEXES
-- =====================================================

CREATE UNIQUE INDEX idx_webhook_events_idempotency_key ON webhook_events(idempotency_key);
CREATE INDEX idx_webhook_events_created_at ON webhook_events(created_at);
CREATE INDEX idx_webhook_events_application_id ON webhook_events(application_id);
CREATE INDEX idx_webhook_events_status ON webhook_events(status, created_at DESC);

-- =====================================================
-- FAILED JOBS INDEXES
-- =====================================================

CREATE INDEX idx_failed_jobs_job_id ON failed_jobs(job_id);
CREATE INDEX idx_failed_jobs_task_name ON failed_jobs(task_name);
CREATE INDEX idx_failed_jobs_status ON failed_jobs(status, created_at DESC);
CREATE INDEX idx_failed_jobs_created_at ON failed_jobs(created_at DESC);

-- =====================================================
-- PENDING JOBS INDEXES
-- =====================================================

CREATE INDEX idx_pending_jobs_application_id ON pending_jobs(application_id);
CREATE INDEX idx_pending_jobs_status ON pending_jobs(status, created_at ASC) WHERE status = 'pending';
CREATE INDEX idx_pending_jobs_created_at ON pending_jobs(created_at ASC);
CREATE INDEX idx_pending_jobs_arq_job_id ON pending_jobs(arq_job_id) WHERE arq_job_id IS NOT NULL;
