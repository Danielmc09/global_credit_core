-- Partitioning Functions
-- Automatic table partitioning for scalability (when tables exceed 1M records)

-- Get table row count
CREATE OR REPLACE FUNCTION get_table_row_count(table_name TEXT)
RETURNS BIGINT AS $$
DECLARE
    row_count BIGINT;
BEGIN
    EXECUTE format('SELECT COUNT(*) FROM %I', table_name) INTO row_count;
    RETURN row_count;
EXCEPTION
    WHEN OTHERS THEN
        RETURN -1;
END;
$$ LANGUAGE plpgsql;

-- Check if table is partitioned
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
        AND c.relkind = 'p'
    ) INTO is_partitioned;
    RETURN is_partitioned;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Create monthly partition
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
    SELECT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = partition_name
        AND n.nspname = 'public'
    ) INTO partition_exists;

    IF partition_exists THEN
        RETURN FALSE;
    END IF;

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

-- Convert table to partitioned table
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
BEGIN
    IF is_table_partitioned(table_name) THEN
        RETURN FALSE;
    END IF;

    temp_table := table_name || '_partitioned_new';

    EXECUTE format(
        'CREATE TABLE %I (LIKE %I INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES) PARTITION BY RANGE (%I)',
        temp_table,
        table_name,
        partition_column
    );

    EXECUTE format(
        'SELECT DATE_TRUNC(''month'', MIN(%I)), DATE_TRUNC(''month'', MAX(%I)) + INTERVAL ''1 month''
         FROM %I',
        partition_column,
        partition_column,
        table_name
    ) INTO partition_start, partition_end;

    IF partition_start IS NULL THEN
        partition_start := DATE_TRUNC('month', CURRENT_DATE);
        partition_end := partition_start + INTERVAL '1 month';
        partition_name := table_name || '_' || TO_CHAR(partition_start, 'YYYY_MM');
        PERFORM create_monthly_partition(temp_table, partition_name, partition_start, partition_end);
    ELSE
        current_month := partition_start;
        WHILE current_month < partition_end LOOP
            month_end := current_month + INTERVAL '1 month';
            partition_name := table_name || '_' || TO_CHAR(current_month, 'YYYY_MM');
            PERFORM create_monthly_partition(temp_table, partition_name, current_month, month_end);
            current_month := month_end;
        END LOOP;
    END IF;

    EXECUTE format('INSERT INTO %I SELECT * FROM %I', temp_table, table_name);
    EXECUTE format('DROP TABLE %I CASCADE', table_name);
    EXECUTE format('ALTER TABLE %I RENAME TO %I', temp_table, table_name);

    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
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

-- Ensure future partitions exist
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
    IF NOT is_table_partitioned(table_name) THEN
        RETURN 0;
    END IF;

    FOR i IN 0..months_ahead-1 LOOP
        partition_date := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
        next_date := partition_date + INTERVAL '1 month';
        partition_name := table_name || '_' || TO_CHAR(partition_date, 'YYYY_MM');

        IF NOT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = partition_name
            AND n.nspname = 'public'
        ) THEN
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

-- Check and partition table if needed (main function)
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
    row_count := get_table_row_count(table_name);
    already_partitioned := is_table_partitioned(table_name);

    result := jsonb_build_object(
        'table_name', table_name,
        'row_count', row_count,
        'threshold', threshold,
        'already_partitioned', already_partitioned,
        'action_taken', 'none',
        'success', false
    );

    IF already_partitioned THEN
        partitions_created := ensure_future_partitions(table_name, 3);
        result := result || jsonb_build_object(
            'action_taken', 'ensure_future_partitions',
            'partitions_created', partitions_created,
            'success', true
        );
        RETURN result;
    END IF;

    IF row_count < threshold THEN
        result := result || jsonb_build_object(
            'action_taken', 'no_action_needed',
            'message', format('Row count (%s) below threshold (%s)', row_count, threshold),
            'success', true
        );
        RETURN result;
    END IF;

    converted := convert_table_to_partitioned(table_name, partition_column);
    
    IF converted THEN
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

-- Function comments
COMMENT ON FUNCTION get_table_row_count(TEXT) IS 'Returns the row count for a given table';
COMMENT ON FUNCTION is_table_partitioned(TEXT) IS 'Checks if a table is already partitioned';
COMMENT ON FUNCTION create_monthly_partition(TEXT, TEXT, DATE, DATE) IS 'Creates a monthly partition for a partitioned table';
COMMENT ON FUNCTION convert_table_to_partitioned(TEXT, TEXT) IS 'Converts a regular table to a partitioned table by range on specified column';
COMMENT ON FUNCTION ensure_future_partitions(TEXT, INTEGER) IS 'Ensures future partitions exist for the next N months';
COMMENT ON FUNCTION check_and_partition_table(TEXT, BIGINT, TEXT) IS 'Checks table row count and partitions if threshold is exceeded';
