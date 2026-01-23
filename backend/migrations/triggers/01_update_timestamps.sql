-- Update Timestamps Triggers
-- Automatically update updated_at column on record changes

-- Applications table
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Webhook events table
CREATE TRIGGER update_webhook_events_updated_at
    BEFORE UPDATE ON webhook_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Failed jobs table
CREATE TRIGGER update_failed_jobs_updated_at
    BEFORE UPDATE ON failed_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Pending jobs table
CREATE TRIGGER update_pending_jobs_updated_at
    BEFORE UPDATE ON pending_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
