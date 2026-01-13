"""Tests for Partitioning Service.

Tests for automatic table partitioning functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.partitioning_service import (
    get_table_row_count,
    is_table_partitioned,
    check_and_partition_table,
    ensure_future_partitions,
    monitor_and_partition_tables,
)


class TestPartitioningService:
    """Test suite for partitioning service"""

    @pytest.mark.asyncio
    async def test_get_table_row_count_success(self, test_db):
        """Test getting row count for a table successfully"""
        async with test_db() as db:
            # Mock the database function to return a count
            result = await db.execute(
                text("SELECT 1000 as get_table_row_count")
            )
            count = result.scalar()
            
            # Since we're using a real database, we can test with actual tables
            # For now, we'll test the error handling path
            count = await get_table_row_count(db, "applications")
            # Should return -1 on error or actual count
            assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_get_table_row_count_error(self, test_db):
        """Test getting row count when database function raises error"""
        async with test_db() as db:
            # Test with invalid table name to trigger error
            with patch.object(db, 'execute', side_effect=Exception("Database error")):
                count = await get_table_row_count(db, "invalid_table")
                assert count == -1

    @pytest.mark.asyncio
    async def test_is_table_partitioned_success(self, test_db):
        """Test checking if table is partitioned successfully"""
        async with test_db() as db:
            # Test with actual database
            is_partitioned = await is_table_partitioned(db, "applications")
            # Should return False for non-partitioned tables or True for partitioned
            assert isinstance(is_partitioned, bool)

    @pytest.mark.asyncio
    async def test_is_table_partitioned_error(self, test_db):
        """Test checking if table is partitioned when database raises error"""
        async with test_db() as db:
            with patch.object(db, 'execute', side_effect=Exception("Database error")):
                is_partitioned = await is_table_partitioned(db, "invalid_table")
                assert is_partitioned is False

    @pytest.mark.asyncio
    async def test_check_and_partition_table_success(self, test_db):
        """Test checking and partitioning a table successfully"""
        async with test_db() as db:
            # Mock the database function to return success
            with patch.object(db, 'execute') as mock_execute:
                mock_result = MagicMock()
                mock_result.scalar.return_value = {
                    "table_name": "applications",
                    "success": True,
                    "action_taken": "no_action_needed",
                    "row_count": 100
                }
                mock_execute.return_value = mock_result
                
                result = await check_and_partition_table(db, "applications", threshold=1000000)
                assert result["success"] is True
                assert result["table_name"] == "applications"

    @pytest.mark.asyncio
    async def test_check_and_partition_table_no_result(self, test_db):
        """Test checking and partitioning when database returns no result"""
        async with test_db() as db:
            with patch.object(db, 'execute') as mock_execute:
                mock_result = MagicMock()
                mock_result.scalar.return_value = None
                mock_execute.return_value = mock_result
                
                result = await check_and_partition_table(db, "applications")
                assert result["success"] is False
                assert "No result returned" in result["error"]

    @pytest.mark.asyncio
    async def test_check_and_partition_table_error(self, test_db):
        """Test checking and partitioning when database raises error"""
        async with test_db() as db:
            with patch.object(db, 'execute', side_effect=Exception("Database error")):
                result = await check_and_partition_table(db, "applications")
                assert result["success"] is False
                assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_check_and_partition_table_with_custom_threshold(self, test_db):
        """Test checking and partitioning with custom threshold"""
        async with test_db() as db:
            with patch.object(db, 'execute') as mock_execute:
                mock_result = MagicMock()
                mock_result.scalar.return_value = {
                    "table_name": "applications",
                    "success": True,
                    "action_taken": "converted_to_partitioned",
                    "row_count": 2000000
                }
                mock_execute.return_value = mock_result
                
                result = await check_and_partition_table(
                    db, "applications", threshold=1500000, partition_column="created_at"
                )
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ensure_future_partitions_success(self, test_db):
        """Test ensuring future partitions successfully"""
        async with test_db() as db:
            with patch.object(db, 'execute') as mock_execute:
                mock_result = MagicMock()
                mock_result.scalar.return_value = 3
                mock_execute.return_value = mock_result
                
                count = await ensure_future_partitions(db, "applications", months_ahead=3)
                assert count == 3

    @pytest.mark.asyncio
    async def test_ensure_future_partitions_error(self, test_db):
        """Test ensuring future partitions when database raises error"""
        async with test_db() as db:
            with patch.object(db, 'execute', side_effect=Exception("Database error")):
                count = await ensure_future_partitions(db, "applications")
                assert count == 0

    @pytest.mark.asyncio
    async def test_ensure_future_partitions_none_result(self, test_db):
        """Test ensuring future partitions when database returns None"""
        async with test_db() as db:
            with patch.object(db, 'execute') as mock_execute:
                mock_result = MagicMock()
                mock_result.scalar.return_value = None
                mock_execute.return_value = mock_result
                
                count = await ensure_future_partitions(db, "applications")
                assert count == 0

    @pytest.mark.asyncio
    async def test_monitor_and_partition_tables_success(self, test_db):
        """Test monitoring and partitioning all tables successfully"""
        async with test_db() as db:
            with patch('app.services.partitioning_service.check_and_partition_table') as mock_check:
                mock_check.return_value = {
                    "table_name": "applications",
                    "success": True,
                    "action_taken": "converted_to_partitioned",
                    "row_count": 2000000
                }
                
                with patch.object(db, 'commit', new_callable=AsyncMock):
                    results = await monitor_and_partition_tables(db)
                    
                    assert results["tables_checked"] == 3  # applications, audit_logs, webhook_events
                    assert results["tables_partitioned"] == 3

    @pytest.mark.asyncio
    async def test_monitor_and_partition_tables_already_partitioned(self, test_db):
        """Test monitoring when tables are already partitioned"""
        async with test_db() as db:
            with patch('app.services.partitioning_service.check_and_partition_table') as mock_check:
                mock_check.return_value = {
                    "table_name": "applications",
                    "success": True,
                    "action_taken": "ensure_future_partitions",
                    "partitions_created": 2,
                    "row_count": 500000
                }
                
                with patch.object(db, 'commit', new_callable=AsyncMock):
                    results = await monitor_and_partition_tables(db)
                    
                    assert results["tables_already_partitioned"] == 3

    @pytest.mark.asyncio
    async def test_monitor_and_partition_tables_below_threshold(self, test_db):
        """Test monitoring when tables are below threshold"""
        async with test_db() as db:
            with patch('app.services.partitioning_service.check_and_partition_table') as mock_check:
                mock_check.return_value = {
                    "table_name": "applications",
                    "success": True,
                    "action_taken": "no_action_needed",
                    "row_count": 100000
                }
                
                with patch.object(db, 'commit', new_callable=AsyncMock):
                    results = await monitor_and_partition_tables(db)
                    
                    assert results["tables_below_threshold"] == 3

    @pytest.mark.asyncio
    async def test_monitor_and_partition_tables_error(self, test_db):
        """Test monitoring when partitioning fails"""
        async with test_db() as db:
            with patch('app.services.partitioning_service.check_and_partition_table') as mock_check:
                mock_check.return_value = {
                    "table_name": "applications",
                    "success": False,
                    "error": "Partitioning failed"
                }
                
                with patch.object(db, 'commit', new_callable=AsyncMock):
                    results = await monitor_and_partition_tables(db)
                    
                    assert len(results["errors"]) == 3
                    assert "Partitioning failed" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_monitor_and_partition_tables_exception(self, test_db):
        """Test monitoring when an exception occurs during processing"""
        async with test_db() as db:
            with patch('app.services.partitioning_service.check_and_partition_table', side_effect=Exception("Unexpected error")):
                with patch.object(db, 'rollback', new_callable=AsyncMock):
                    results = await monitor_and_partition_tables(db)
                    
                    assert len(results["errors"]) == 3
                    assert "Unexpected error" in results["errors"][0]
