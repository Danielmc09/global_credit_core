-- Job Queue Trigger
-- CRITICAL: DB Trigger -> Queue flow (Requirement 3.7)

-- Function to enqueue application processing
CREATE OR REPLACE FUNCTION enqueue_application_processing()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'PENDING' THEN
        INSERT INTO pending_jobs (
            application_id,
            task_name,
            job_args,
            status,
            created_at
        ) VALUES (
            NEW.id,
            'process_credit_application',
            jsonb_build_object(
                'application_id', NEW.id::text,
                'country', NEW.country::text,
                'triggered_by', 'database_trigger',
                'triggered_at', CURRENT_TIMESTAMP
            ),
            'pending',
            CURRENT_TIMESTAMP
        );
        
        RAISE NOTICE 'DB Trigger: Created pending_job for application % (Requirement 3.7)', NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger that fires AFTER INSERT on applications
CREATE TRIGGER trigger_enqueue_application_processing
    AFTER INSERT ON applications
    FOR EACH ROW
    WHEN (NEW.status = 'PENDING')
    EXECUTE FUNCTION enqueue_application_processing();

-- Comments
COMMENT ON FUNCTION enqueue_application_processing() IS 'CRITICAL: DB Trigger that creates pending_job when application is INSERTED. Implements Requirement 3.7';
COMMENT ON TRIGGER trigger_enqueue_application_processing ON applications IS 'CRITICAL: Automatically creates pending_job when new application is INSERTED (Requirement 3.7)';
