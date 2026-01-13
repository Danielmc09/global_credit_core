"""
Tests for Currency Validation by Country

Tests that validate currency matches country requirements:
- Reject incorrect currency (e.g., EUR for Brazil)
- Accept correct currency
- Infer currency if not specified
"""

import pytest
from sqlalchemy import select

from app.core.constants import Currency
from app.models.application import Application


class TestCurrencyValidation:
    """Test suite for currency validation by country"""

    @pytest.mark.asyncio()
    async def test_reject_eur_for_brazil(self, client, auth_headers):
        """Test that EUR is rejected for Brazil (should be BRL)"""
        payload = {
            "country": "BR",
            "full_name": "João Silva Santos",
            "identity_document": "11144477735",  # Valid CPF with correct checksum
            "requested_amount": 50000.00,
            "monthly_income": 5000.00,
            "currency": "EUR",  # Wrong currency for Brazil
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 422  # Validation error
        error_data = response.json()
        # FastAPI returns detail as list or string
        if isinstance(error_data["detail"], list):
            error_detail = " ".join([str(err.get("msg", "")) for err in error_data["detail"]])
        else:
            error_detail = str(error_data["detail"])
        # Check that error mentions currency mismatch
        error_lower = error_detail.lower()
        assert "currency" in error_lower or "eur" in error_lower
        assert "brl" in error_lower or "brazil" in error_lower

    @pytest.mark.asyncio()
    async def test_reject_brl_for_spain(self, client, auth_headers):
        """Test that BRL is rejected for Spain (should be EUR)"""
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
            "currency": "BRL",  # Wrong currency for Spain
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 422  # Validation error
        error_data = response.json()
        # FastAPI returns detail as list or string
        if isinstance(error_data["detail"], list):
            error_detail = " ".join([str(err.get("msg", "")) for err in error_data["detail"]])
        else:
            error_detail = str(error_data["detail"])
        error_lower = error_detail.lower()
        assert "currency" in error_lower or "brl" in error_lower
        assert "eur" in error_lower or "spain" in error_lower

    @pytest.mark.asyncio()
    async def test_accept_correct_currency_brazil(self, client, auth_headers):
        """Test that correct currency (BRL) is accepted for Brazil"""
        payload = {
            "country": "BR",
            "full_name": "João Silva Santos",
            "identity_document": "11144477735",  # Valid CPF with correct checksum
            "requested_amount": 50000.00,
            "monthly_income": 5000.00,
            "currency": "BRL",  # Correct currency
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "BRL"
        assert data["country"] == "BR"

    @pytest.mark.asyncio()
    async def test_accept_correct_currency_spain(self, client, auth_headers):
        """Test that correct currency (EUR) is accepted for Spain"""
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
            "currency": "EUR",  # Correct currency
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "EUR"
        assert data["country"] == "ES"

    @pytest.mark.asyncio()
    async def test_infer_currency_when_not_specified_brazil(self, client, auth_headers):
        """Test that currency is inferred from country when not specified (Brazil -> BRL)"""
        payload = {
            "country": "BR",
            "full_name": "João Silva Santos",
            "identity_document": "11144477735",  # Valid CPF with correct checksum
            "requested_amount": 50000.00,
            "monthly_income": 5000.00,
            # currency not specified - should be inferred as BRL
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "BRL"  # Should be inferred
        assert data["country"] == "BR"

    @pytest.mark.asyncio()
    async def test_infer_currency_when_not_specified_spain(self, client, auth_headers):
        """Test that currency is inferred from country when not specified (Spain -> EUR)"""
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
            # currency not specified - should be inferred as EUR
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "EUR"  # Should be inferred
        assert data["country"] == "ES"

    @pytest.mark.asyncio()
    async def test_infer_currency_all_countries(self, client, auth_headers):
        """Test currency inference for all supported countries"""
        test_cases = [
            ("ES", Currency.EUR),
            ("PT", Currency.EUR),
            ("IT", Currency.EUR),
            ("BR", Currency.BRL),
            ("MX", Currency.MXN),
            ("CO", Currency.COP),
        ]

        for country_code, expected_currency in test_cases:
            # Get valid document format for each country
            documents = {
                "ES": "12345678Z",
                "PT": "123456789",
                "IT": "RSSMRA80A01H501U",
                "BR": "11144477735",  # Valid CPF with correct checksum
                "MX": "HERM850101MDFRRR01",
                "CO": "1234567890",
            }

            # Use country-specific minimum income requirements
            min_incomes = {
                "ES": 1500.00,
                "PT": 800.00,
                "IT": 1200.00,
                "BR": 2000.00,
                "MX": 5000.00,  # Mexico minimum income
                "CO": 1500000.00,  # Colombia minimum income (COP)
            }

            payload = {
                "country": country_code,
                "full_name": "Test User Name",
                "identity_document": documents[country_code],
                "requested_amount": 10000.00,
                "monthly_income": min_incomes.get(country_code, 3000.00),
                # currency not specified
                "country_specific_data": {}
            }

            response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

            assert response.status_code == 201, f"Failed for country {country_code}"
            data = response.json()
            assert data["currency"] == expected_currency, \
                f"Expected {expected_currency} for {country_code}, got {data['currency']}"

    @pytest.mark.asyncio()
    async def test_currency_persisted_in_database(self, client, auth_headers, test_db):
        """Test that currency is correctly persisted in the database"""

        payload = {
            "country": "BR",
            "full_name": "João Silva Santos",
            "identity_document": "11144477735",  # Valid CPF with correct checksum
            "requested_amount": 50000.00,
            "monthly_income": 5000.00,
            "currency": "BRL",
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response.status_code == 201
        app_id = response.json()["id"]

        # Query database directly using a session from the factory
        async with test_db() as session:
            result = await session.execute(
                select(Application).where(Application.id == app_id)
            )
            application = result.scalar_one()

            assert application.currency == "BRL"
            assert application.country == "BR"

    @pytest.mark.asyncio()
    async def test_currency_in_response_after_creation(self, client, auth_headers):
        """Test that currency appears in API response after creation"""
        payload = {
            "country": "MX",
            "full_name": "María Hernández",
            "identity_document": "HERM850101MDFRRR01",
            "requested_amount": 50000.00,
            "monthly_income": 12000.00,
            "currency": "MXN",
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
        data = response.json()

        # Currency should be in response
        assert "currency" in data
        assert data["currency"] == "MXN"

        # Verify by getting the application
        app_id = data["id"]
        get_response = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["currency"] == "MXN"
