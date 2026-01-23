-- Views
-- Commonly used views for easier querying

-- Active applications view (non-deleted)
CREATE VIEW active_applications AS
SELECT * FROM applications
WHERE deleted_at IS NULL
ORDER BY created_at DESC;

COMMENT ON VIEW active_applications IS 'Non-deleted applications ordered by creation date';
