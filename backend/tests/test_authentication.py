"""
Tests for authentication and authorization.

Verifies that endpoints are properly protected with JWT authentication
and that role-based access control (RBAC) is enforced.
"""

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_application_without_auth(client: AsyncClient):
    """Test that creating application without auth returns 401"""
    payload = {
        "country": "ES",
        "full_name": "Test User",
        "identity_document": "12345678Z",
        "requested_amount": 10000.00,
        "monthly_income": 3000.00
    }
    
    response = await client.post("/api/v1/applications", json=payload)
    
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_list_applications_without_auth(client: AsyncClient):
    """Test that listing applications without auth returns 401"""
    response = await client.get("/api/v1/applications")
    
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_get_application_without_auth(client: AsyncClient, sample_application):
    """Test that getting application without auth returns 401"""
    response = await client.get(f"/api/v1/applications/{sample_application}")
    
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_update_application_without_auth(client: AsyncClient, sample_application):
    """Test that updating application without auth returns 401"""
    response = await client.patch(
        f"/api/v1/applications/{sample_application}",
        json={"status": "APPROVED"}
    )
    
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_delete_application_without_auth(client: AsyncClient, sample_application):
    """Test that deleting application without auth returns 401"""
    response = await client.delete(f"/api/v1/applications/{sample_application}")
    
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_update_application_without_admin(client: AsyncClient, auth_headers, sample_application):
    """Test that updating application without admin role returns 403"""
    # Try to update without admin role (using regular user token)
    response = await client.patch(
        f"/api/v1/applications/{sample_application}",
        json={"status": "APPROVED"},
        headers=auth_headers  # Regular user, not admin
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_application_without_admin(client: AsyncClient, auth_headers, sample_application):
    """Test that deleting application without admin role returns 403"""
    # Try to delete without admin role (using regular user token)
    response = await client.delete(
        f"/api/v1/applications/{sample_application}",
        headers=auth_headers  # Regular user, not admin
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_application_with_admin(client: AsyncClient, admin_headers):
    """Test that updating application with admin role succeeds"""
    # First create application with admin (admin can also create)
    create_response = await client.post(
        "/api/v1/applications",
        json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "99999999R",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00
        },
        headers=admin_headers
    )
    
    assert create_response.status_code == 201
    app_id = create_response.json()["id"]
    
    # Update with admin role - change to VALIDATING (valid transition from PENDING)
    update_response = await client.patch(
        f"/api/v1/applications/{app_id}",
        json={"status": "VALIDATING"},
        headers=admin_headers
    )
    
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "VALIDATING"


@pytest.mark.asyncio
async def test_delete_application_with_admin(client: AsyncClient, admin_headers):
    """Test that deleting application with admin role succeeds"""
    # First create application
    create_response = await client.post(
        "/api/v1/applications",
        json={
            "country": "ES",
            "full_name": "Test User Delete",
            "identity_document": "88888888Y",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00
        },
        headers=admin_headers
    )
    
    assert create_response.status_code == 201
    app_id = create_response.json()["id"]
    
    # Delete with admin role
    delete_response = await client.delete(
        f"/api/v1/applications/{app_id}",
        headers=admin_headers
    )
    
    assert delete_response.status_code == 200


@pytest.mark.asyncio
async def test_create_application_with_auth(client: AsyncClient, auth_headers):
    """Test that creating application with valid auth succeeds"""
    payload = {
        "country": "ES",
        "full_name": "Test User Auth",
        "identity_document": "77777777B",
        "requested_amount": 10000.00,
        "monthly_income": 3000.00
    }
    
    response = await client.post(
        "/api/v1/applications",
        json=payload,
        headers=auth_headers
    )
    
    assert response.status_code == 201
    assert response.json()["country"] == "ES"


@pytest.mark.asyncio
async def test_list_applications_with_auth(client: AsyncClient, auth_headers):
    """Test that listing applications with valid auth succeeds"""
    response = await client.get(
        "/api/v1/applications",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert "applications" in response.json()
    assert "total" in response.json()
