-- Statistics Functions
-- Business intelligence and reporting functions

-- Get application statistics by country
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

COMMENT ON FUNCTION get_country_statistics(country_code) IS 'Returns application statistics for a specific country';
