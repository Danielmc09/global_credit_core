-- Extensions
-- Enable required PostgreSQL extensions for the application

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- PII encryption (CRITICAL for production)
-- Provides encryption functions for sensitive data at rest
CREATE EXTENSION IF NOT EXISTS pgcrypto;
