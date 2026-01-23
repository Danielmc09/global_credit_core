-- Audit Logging Trigger
-- CRITICAL: Automatic audit trail for application status changes

-- Function to log status changes
CREATE OR REPLACE FUNCTION log_status_change()
RETURNS TRIGGER AS $$
BEGIN
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
            COALESCE(current_setting('app.changed_by', true), 'system'),
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

-- Comments
COMMENT ON FUNCTION log_status_change() IS 'Automatically creates audit log when application status changes';
COMMENT ON TRIGGER audit_status_change ON applications IS 'Automatic audit logging for status changes';
