"""Partitioning Service.

Automatically partitions tables when they exceed 1M records.
Uses PostgreSQL native partitioning by range on created_at column.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.constants import DatabaseLimits
from ..core.logging import get_logger

logger = get_logger(__name__)

# Tables to monitor for partitioning
PARTITIONABLE_TABLES = [
    {
        "name": "applications",
        "partition_column": "created_at",
        "threshold": DatabaseLimits.PARTITION_THRESHOLD,
    },
    {
        "name": "audit_logs",
        "partition_column": "created_at",
        "threshold": DatabaseLimits.PARTITION_THRESHOLD,
    },
    {
        "name": "webhook_events",
        "partition_column": "created_at",
        "threshold": DatabaseLimits.PARTITION_THRESHOLD,
    },
]


async def get_table_row_count(session: AsyncSession, table_name: str) -> int:
    """Get the row count for a table.

    Args:
        session: Database session
        table_name: Name of the table

    Returns:
        Row count, or -1 on error
    """
    try:
        result = await session.execute(
            text("SELECT get_table_row_count(:table_name)"),
            {"table_name": table_name}
        )
        count = result.scalar()
        return int(count) if count is not None else -1
    except Exception as e:
        logger.error(f"Error getting row count for {table_name}: {e}")
        return -1


async def is_table_partitioned(session: AsyncSession, table_name: str) -> bool:
    """Check if a table is already partitioned.

    Args:
        session: Database session
        table_name: Name of the table

    Returns:
        True if table is partitioned, False otherwise
    """
    try:
        result = await session.execute(
            text("SELECT is_table_partitioned(:table_name)"),
            {"table_name": table_name}
        )
        is_partitioned = result.scalar()
        return bool(is_partitioned) if is_partitioned is not None else False
    except Exception as e:
        logger.error(f"Error checking if {table_name} is partitioned: {e}")
        return False


async def check_and_partition_table(
    session: AsyncSession,
    table_name: str,
    threshold: int | None = None,
    partition_column: str = "created_at"
) -> dict[str, Any]:
    """Check table row count and partition if threshold is exceeded.

    Args:
        session: Database session
        table_name: Name of the table to check
        threshold: Row count threshold (defaults to DatabaseLimits.PARTITION_THRESHOLD)
        partition_column: Column to use for partitioning (default: created_at)

    Returns:
        Dictionary with operation results
    """
    if threshold is None:
        threshold = DatabaseLimits.PARTITION_THRESHOLD

    try:
        result = await session.execute(
            text("SELECT check_and_partition_table(:table_name, :threshold, :partition_column)"),
            {
                "table_name": table_name,
                "threshold": threshold,
                "partition_column": partition_column,
            }
        )
        result_json = result.scalar()
        
        # Parse JSONB result
        if result_json:
            return dict(result_json)
        else:
            return {
                "table_name": table_name,
                "success": False,
                "error": "No result returned from database function"
            }
    except Exception as e:
        logger.error(f"Error checking/partitioning table {table_name}: {e}")
        return {
            "table_name": table_name,
            "success": False,
            "error": str(e)
        }


async def ensure_future_partitions(
    session: AsyncSession,
    table_name: str,
    months_ahead: int = 3
) -> int:
    """Ensure future partitions exist for a partitioned table.

    Args:
        session: Database session
        table_name: Name of the partitioned table
        months_ahead: Number of months ahead to create partitions

    Returns:
        Number of partitions created
    """
    try:
        result = await session.execute(
            text("SELECT ensure_future_partitions(:table_name, :months_ahead)"),
            {
                "table_name": table_name,
                "months_ahead": months_ahead,
            }
        )
        count = result.scalar()
        return int(count) if count is not None else 0
    except Exception as e:
        logger.error(f"Error ensuring future partitions for {table_name}: {e}")
        return 0


async def monitor_and_partition_tables(session: AsyncSession) -> dict[str, Any]:
    """Monitor all partitionable tables and partition if needed.

    This function:
    1. Checks each table's row count
    2. Partitions tables that exceed the threshold
    3. Ensures future partitions exist for already-partitioned tables

    Args:
        session: Database session

    Returns:
        Dictionary with results for each table
    """
    results = {
        "tables_checked": 0,
        "tables_partitioned": 0,
        "tables_already_partitioned": 0,
        "tables_below_threshold": 0,
        "errors": [],
        "details": {},
    }

    for table_config in PARTITIONABLE_TABLES:
        table_name = table_config["name"]
        threshold = table_config["threshold"]
        partition_column = table_config["partition_column"]

        results["tables_checked"] += 1

        try:
            logger.info(f"Checking table {table_name} for partitioning (threshold: {threshold:,})")

            # Check and partition
            result = await check_and_partition_table(
                session,
                table_name,
                threshold=threshold,
                partition_column=partition_column
            )

            results["details"][table_name] = result

            if result.get("success"):
                action = result.get("action_taken", "unknown")
                
                if action == "converted_to_partitioned":
                    results["tables_partitioned"] += 1
                    logger.info(
                        f"✓ Table {table_name} converted to partitioned table "
                        f"(row count: {result.get('row_count', 'unknown'):,})"
                    )
                elif action == "ensure_future_partitions":
                    results["tables_already_partitioned"] += 1
                    partitions_created = result.get("partitions_created", 0)
                    if partitions_created > 0:
                        logger.info(
                            f"✓ Table {table_name} already partitioned, "
                            f"created {partitions_created} future partition(s)"
                        )
                    else:
                        logger.debug(
                            f"Table {table_name} already partitioned, "
                            "all future partitions exist"
                        )
                elif action == "no_action_needed":
                    results["tables_below_threshold"] += 1
                    logger.debug(
                        f"Table {table_name} below threshold "
                        f"({result.get('row_count', 'unknown'):,} < {threshold:,})"
                    )
            else:
                error_msg = result.get("error_message") or result.get("error", "Unknown error")
                results["errors"].append(f"{table_name}: {error_msg}")
                logger.error(f"✗ Failed to partition table {table_name}: {error_msg}")

            # Commit after each table to ensure changes are persisted
            await session.commit()

        except Exception as e:
            error_msg = f"Error processing table {table_name}: {str(e)}"
            results["errors"].append(error_msg)
            results["details"][table_name] = {
                "table_name": table_name,
                "success": False,
                "error": error_msg
            }
            logger.error(f"✗ {error_msg}")
            # Rollback on error
            await session.rollback()

    logger.info(
        f"Partitioning check completed: "
        f"{results['tables_checked']} tables checked, "
        f"{results['tables_partitioned']} partitioned, "
        f"{results['tables_already_partitioned']} already partitioned, "
        f"{results['tables_below_threshold']} below threshold, "
        f"{len(results['errors'])} errors"
    )

    return results
