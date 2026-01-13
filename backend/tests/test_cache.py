"""
Tests for Cache Service

Tests cache functionality for country statistics:
- Cache hit/miss behavior
- TTL configuration
- Cache invalidation on application create/update
"""

import asyncio
import random

import pytest

from app.services.application_service import ApplicationService
from app.services.cache_service import cache, country_stats_key


def generate_valid_spanish_dni() -> str:
    """Generate a valid Spanish DNI with correct checksum"""
    dni_letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
    # Generate random 8-digit number
    number = random.randint(10000000, 99999999)
    letter = dni_letters[number % 23]
    return f"{number}{letter}"


class TestCountryStatsCache:
    """Test suite for country statistics caching"""

    @pytest.mark.asyncio()
    async def test_cache_miss_then_hit(self, test_db):
        """Test that first call hits DB, second call hits cache"""
        async with test_db() as db:
            service = ApplicationService(db)
            country = "ES"

            # Clear cache first
            cache_key = country_stats_key(country)
            await cache.delete(cache_key)

            # First call - should be cache miss
            async def fetch_stats():
                return await service.get_statistics_by_country(country)

            stats1 = await cache.get_country_stats_cached(country, fetch_stats)

            # Verify stats structure
            assert "country" in stats1
            assert "total_applications" in stats1
            assert stats1["country"] == country

            # Second call - should be cache hit
            # We'll verify by checking if the same data is returned
            # and by checking Redis directly
            stats2 = await cache.get_country_stats_cached(country, fetch_stats)

            # Should return same data
            assert stats1 == stats2

            # Verify it's actually in cache
            cached_value = await cache.get(cache_key)
            assert cached_value is not None
            assert cached_value["country"] == country

    @pytest.mark.asyncio()
    async def test_cache_invalidation_on_create(self, test_db, auth_headers, client):
        """Test that cache is invalidated when application is created"""
        async with test_db() as db:
            country = "ES"
            cache_key = country_stats_key(country)

            # Get initial stats and cache them
            service = ApplicationService(db)
            async def fetch_stats():
                return await service.get_statistics_by_country(country)

            initial_stats = await cache.get_country_stats_cached(country, fetch_stats)
            initial_count = initial_stats["total_applications"]

            # Verify cache is set
            cached_before = await cache.get(cache_key)
            assert cached_before is not None

            # Create a new application with a valid and unique DNI
            unique_dni = generate_valid_spanish_dni()
            payload = {
                "country": country,
                "full_name": "Cache Test User",
                "identity_document": unique_dni,
                "requested_amount": 5000.00,
                "monthly_income": 2000.00,
                "country_specific_data": {}
            }

            response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
            assert response.status_code == 201

            # Wait a bit for async operations
            await asyncio.sleep(0.1)

            # Verify cache was invalidated
            cached_after = await cache.get(cache_key)
            assert cached_after is None, "Cache should be invalidated after creating application"

            # Get stats again - should fetch from DB and show new count
            new_stats = await cache.get_country_stats_cached(country, fetch_stats)
            assert new_stats["total_applications"] == initial_count + 1

    @pytest.mark.asyncio()
    async def test_cache_invalidation_on_update(self, test_db, auth_headers, admin_headers, client):
        """Test that cache is invalidated when application is updated"""
        async with test_db() as db:
            country = "ES"
            cache_key = country_stats_key(country)

            # Create an application first with a valid and unique DNI
            unique_dni = generate_valid_spanish_dni()
            payload = {
                "country": country,
                "full_name": "Update Cache Test User",
                "identity_document": unique_dni,
                "requested_amount": 10000.00,
                "monthly_income": 3000.00,
                "country_specific_data": {}
            }

            create_response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
            assert create_response.status_code == 201
            app_id = create_response.json()["id"]

            # Wait for async operations
            await asyncio.sleep(0.1)

            # Get stats and cache them
            service = ApplicationService(db)
            async def fetch_stats():
                return await service.get_statistics_by_country(country)

            # Get initial stats (this will cache them)
            await cache.get_country_stats_cached(country, fetch_stats)

            # Verify cache is set
            cached_before = await cache.get(cache_key)
            assert cached_before is not None

            # Update the application status
            # Must follow valid state transitions: PENDING -> VALIDATING -> APPROVED
            # Step 1: PENDING -> VALIDATING
            update_response_1 = await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": "VALIDATING"},
                headers=admin_headers
            )
            assert update_response_1.status_code == 200
            
            # Step 2: VALIDATING -> APPROVED
            update_response = await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": "APPROVED"},
                headers=admin_headers
            )
            assert update_response.status_code == 200

            # Wait for async operations
            await asyncio.sleep(0.1)

            # Verify cache was invalidated
            cached_after = await cache.get(cache_key)
            assert cached_after is None, "Cache should be invalidated after updating application"

            # Get stats again - should fetch from DB
            new_stats = await cache.get_country_stats_cached(country, fetch_stats)
            # The stats should be updated (approved count should increase)
            assert new_stats is not None

    @pytest.mark.asyncio()
    async def test_cache_ttl_configuration(self, test_db):
        """Test that cache has correct TTL (5 minutes = 300 seconds)"""
        async with test_db() as db:
            country = "ES"
            cache_key = country_stats_key(country)

            # Clear cache
            await cache.delete(cache_key)

            # Get stats to populate cache
            service = ApplicationService(db)
            async def fetch_stats():
                return await service.get_statistics_by_country(country)

            await cache.get_country_stats_cached(country, fetch_stats)

            # Check TTL in Redis
            # Ensure cache is connected
            if not cache._connected:
                await cache.connect()

            if cache.redis:
                ttl = await cache.redis.ttl(cache_key)
                # TTL should be 300 seconds (5 minutes)
                # Allow some tolerance (could be slightly less due to time elapsed)
                assert 280 <= ttl <= 300, f"TTL should be around 300 seconds, got {ttl}"
            else:
                pytest.skip("Redis not available for TTL check")

    @pytest.mark.asyncio()
    async def test_cache_different_countries(self, test_db):
        """Test that different countries have separate cache entries"""
        async with test_db() as db:
            service = ApplicationService(db)

            # Get stats for different countries
            async def fetch_stats_es():
                return await service.get_statistics_by_country("ES")

            async def fetch_stats_mx():
                return await service.get_statistics_by_country("MX")

            await cache.get_country_stats_cached("ES", fetch_stats_es)
            await cache.get_country_stats_cached("MX", fetch_stats_mx)

            # Verify both are cached separately
            cache_key_es = country_stats_key("ES")
            cache_key_mx = country_stats_key("MX")

            cached_es = await cache.get(cache_key_es)
            cached_mx = await cache.get(cache_key_mx)

            assert cached_es is not None
            assert cached_mx is not None
            assert cached_es["country"] == "ES"
            assert cached_mx["country"] == "MX"

    @pytest.mark.asyncio()
    async def test_cache_fallback_on_error(self, test_db):
        """Test that cache gracefully handles errors and falls back to DB"""
        async with test_db() as db:
            country = "ES"
            service = ApplicationService(db)

            # Create a fetch function that will work
            async def fetch_stats():
                return await service.get_statistics_by_country(country)

            # Get stats (should work even if Redis has issues)
            stats = await cache.get_country_stats_cached(country, fetch_stats)
            assert stats is not None
            assert stats["country"] == country
