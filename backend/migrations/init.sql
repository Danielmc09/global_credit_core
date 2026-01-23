-- =====================================================
-- Global Credit Core - Database Initialization
-- =====================================================
-- Multi-country credit application system
-- 
-- This master script orchestrates the database setup by
-- executing modular SQL files in the correct order.
-- 
-- Structure:
--   schemas/    - Tables, indexes, views, types
--   functions/  - SQL functions
--   triggers/   - Automatic triggers
-- =====================================================

-- Create test database
SELECT 'CREATE DATABASE credit_db_test' 
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'credit_db_test')\gexec

-- =====================================================
-- STEP 1: Extensions
-- =====================================================
\echo '=== Installing Extensions ==='
\i /migrations/schemas/01_extensions.sql

-- =====================================================
-- STEP 2: Types
-- =====================================================
\echo '=== Creating Types ==='
\i /migrations/schemas/02_types.sql

-- =====================================================
-- STEP 3: Tables
-- =====================================================
\echo '=== Creating Tables ==='
\i /migrations/schemas/03_tables.sql

-- =====================================================
-- STEP 4: Indexes
-- =====================================================
\echo '=== Creating Indexes ==='
\i /migrations/schemas/04_indexes.sql

-- =====================================================
-- STEP 5: Views
-- =====================================================
\echo '=== Creating Views ==='
\i /migrations/schemas/05_views.sql

-- =====================================================
-- STEP 6: Functions
-- =====================================================
\echo '=== Creating Functions ==='
\i /migrations/functions/01_basic_functions.sql
\i /migrations/functions/02_partitioning_functions.sql
\i /migrations/functions/03_statistics_functions.sql

-- =====================================================
-- STEP 7: Triggers
-- =====================================================
\echo '=== Creating Triggers ==='
\i /migrations/triggers/01_update_timestamps.sql
\i /migrations/triggers/02_audit_logging.sql
\i /migrations/triggers/03_job_queue.sql

-- =====================================================
-- STEP 8: Permissions
-- =====================================================
\echo '=== Granting Permissions ==='

-- Grant table permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO credit_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO credit_user;

-- Grant function permissions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO credit_user;

-- =====================================================
-- Initialization Complete
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Database Initialization Completed!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Created:';
    RAISE NOTICE '  - 5 tables (applications, audit_logs, webhook_events, failed_jobs, pending_jobs)';
    RAISE NOTICE '  - 20+ indexes for performance';
    RAISE NOTICE '  - 1 view (active_applications)';
    RAISE NOTICE '  - 8 functions (partitioning, statistics)';
    RAISE NOTICE '  - 6 triggers (audit, timestamps, job queue)';
    RAISE NOTICE '';
    RAISE NOTICE 'Security:';
    RAISE NOTICE '  ✓ PII fields encrypted (BYTEA with pgcrypto)';
    RAISE NOTICE '  ✓ Set ENCRYPTION_KEY env var (min 32 chars)';
    RAISE NOTICE '';
    RAISE NOTICE 'Features:';
    RAISE NOTICE '  ✓ Automatic audit logging';
    RAISE NOTICE '  ✓ DB Trigger -> Job Queue (Requirement 3.7)';
    RAISE NOTICE '  ✓ Automatic partitioning (when > 1M records)';
    RAISE NOTICE '  ✓ Idempotency protection';
    RAISE NOTICE '  ✓ Soft deletes';
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
END $$;
