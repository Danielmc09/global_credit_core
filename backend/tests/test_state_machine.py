"""
Tests for Application State Machine

Tests validate that state transitions follow the defined state machine rules.
"""

import pytest

from app.core.state_machine import (
    FINAL_STATES,
    get_allowed_transitions,
    is_final_state,
    validate_transition,
)
from app.models.application import ApplicationStatus


class TestStateMachineValidation:
    """Test suite for state machine validation functions"""

    def test_validate_transition_pending_to_validating(self):
        """Test: Valid transition from PENDING to VALIDATING"""
        validate_transition(ApplicationStatus.PENDING, ApplicationStatus.VALIDATING)
        # Should not raise

    def test_validate_transition_pending_to_cancelled(self):
        """Test: Valid transition from PENDING to CANCELLED"""
        validate_transition(ApplicationStatus.PENDING, ApplicationStatus.CANCELLED)
        # Should not raise

    def test_validate_transition_validating_to_approved(self):
        """Test: Valid transition from VALIDATING to APPROVED"""
        validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.APPROVED)
        # Should not raise

    def test_validate_transition_validating_to_rejected(self):
        """Test: Valid transition from VALIDATING to REJECTED"""
        validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.REJECTED)
        # Should not raise

    def test_validate_transition_validating_to_under_review(self):
        """Test: Valid transition from VALIDATING to UNDER_REVIEW"""
        validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.UNDER_REVIEW)
        # Should not raise

    def test_validate_transition_under_review_to_approved(self):
        """Test: Valid transition from UNDER_REVIEW to APPROVED"""
        validate_transition(ApplicationStatus.UNDER_REVIEW, ApplicationStatus.APPROVED)
        # Should not raise

    def test_validate_transition_under_review_to_rejected(self):
        """Test: Valid transition from UNDER_REVIEW to REJECTED"""
        validate_transition(ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REJECTED)
        # Should not raise

    def test_validate_transition_same_status(self):
        """Test: Same status transition is allowed (no-op)"""
        validate_transition(ApplicationStatus.PENDING, ApplicationStatus.PENDING)
        validate_transition(ApplicationStatus.APPROVED, ApplicationStatus.APPROVED)
        # Should not raise

    def test_validate_transition_invalid_pending_to_approved(self):
        """Test: Invalid transition from PENDING to APPROVED (must go through VALIDATING)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.PENDING, ApplicationStatus.APPROVED)
        assert "Invalid state transition" in str(exc_info.value)
        assert "PENDING" in str(exc_info.value)
        assert "APPROVED" in str(exc_info.value)

    def test_validate_transition_invalid_validating_to_pending(self):
        """Test: Invalid backward transition from VALIDATING to PENDING"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.PENDING)
        assert "Invalid state transition" in str(exc_info.value)

    def test_validate_transition_invalid_approved_to_pending(self):
        """Test: Invalid transition from APPROVED (final state) to PENDING"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.APPROVED, ApplicationStatus.PENDING)
        assert "Cannot change status from final state" in str(exc_info.value)

    def test_validate_transition_invalid_rejected_to_approved(self):
        """Test: Invalid transition from REJECTED (final state) to APPROVED"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.REJECTED, ApplicationStatus.APPROVED)
        assert "Cannot change status from final state" in str(exc_info.value)

    def test_validate_transition_invalid_cancelled_to_validating(self):
        """Test: Invalid transition from CANCELLED (final state) to VALIDATING"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.CANCELLED, ApplicationStatus.VALIDATING)
        assert "Cannot change status from final state" in str(exc_info.value)

    def test_validate_transition_invalid_completed_to_approved(self):
        """Test: Invalid transition from COMPLETED (final state) to APPROVED"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.COMPLETED, ApplicationStatus.APPROVED)
        assert "Cannot change status from final state" in str(exc_info.value)

    def test_is_final_state_approved(self):
        """Test: APPROVED is a final state"""
        assert is_final_state(ApplicationStatus.APPROVED) is True

    def test_is_final_state_rejected(self):
        """Test: REJECTED is a final state"""
        assert is_final_state(ApplicationStatus.REJECTED) is True

    def test_is_final_state_cancelled(self):
        """Test: CANCELLED is a final state"""
        assert is_final_state(ApplicationStatus.CANCELLED) is True

    def test_is_final_state_completed(self):
        """Test: COMPLETED is a final state"""
        assert is_final_state(ApplicationStatus.COMPLETED) is True

    def test_is_final_state_pending(self):
        """Test: PENDING is not a final state"""
        assert is_final_state(ApplicationStatus.PENDING) is False

    def test_is_final_state_validating(self):
        """Test: VALIDATING is not a final state"""
        assert is_final_state(ApplicationStatus.VALIDATING) is False

    def test_is_final_state_under_review(self):
        """Test: UNDER_REVIEW is not a final state"""
        assert is_final_state(ApplicationStatus.UNDER_REVIEW) is False

    def test_get_allowed_transitions_pending(self):
        """Test: Get allowed transitions from PENDING"""
        allowed = get_allowed_transitions(ApplicationStatus.PENDING)
        assert ApplicationStatus.VALIDATING in allowed
        assert ApplicationStatus.CANCELLED in allowed
        assert len(allowed) == 2

    def test_get_allowed_transitions_validating(self):
        """Test: Get allowed transitions from VALIDATING"""
        allowed = get_allowed_transitions(ApplicationStatus.VALIDATING)
        assert ApplicationStatus.APPROVED in allowed
        assert ApplicationStatus.REJECTED in allowed
        assert ApplicationStatus.UNDER_REVIEW in allowed
        assert len(allowed) == 3

    def test_get_allowed_transitions_under_review(self):
        """Test: Get allowed transitions from UNDER_REVIEW"""
        allowed = get_allowed_transitions(ApplicationStatus.UNDER_REVIEW)
        assert ApplicationStatus.APPROVED in allowed
        assert ApplicationStatus.REJECTED in allowed
        assert len(allowed) == 2

    def test_get_allowed_transitions_final_states(self):
        """Test: Final states have no allowed transitions"""
        for final_state in FINAL_STATES:
            allowed = get_allowed_transitions(final_state)
            assert allowed == []


class TestStateMachineIntegration:
    """Test suite for state machine integration with service layer"""

    @pytest.mark.asyncio()
    async def test_update_application_valid_transition(self, client, auth_headers, admin_headers):
        """Test: Update application with valid state transition"""
        # Create application
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
        }
        create_response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert create_response.status_code == 201
        application_id = create_response.json()["id"]

        # Update status from PENDING to VALIDATING (valid transition)
        # Note: Update endpoint requires admin permissions
        update_payload = {"status": "VALIDATING"}
        update_response = await client.patch(
            f"/api/v1/applications/{application_id}",
            json=update_payload,
            headers=admin_headers
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "VALIDATING"

    @pytest.mark.asyncio()
    async def test_update_application_invalid_transition(self, client, auth_headers, admin_headers):
        """Test: Update application with invalid state transition"""
        # Create application
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
        }
        create_response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert create_response.status_code == 201
        application_id = create_response.json()["id"]

        # Try to update status from PENDING to APPROVED (invalid - must go through VALIDATING)
        # Note: Update endpoint requires admin permissions
        update_payload = {"status": "APPROVED"}
        update_response = await client.patch(
            f"/api/v1/applications/{application_id}",
            json=update_payload,
            headers=admin_headers
        )
        assert update_response.status_code == 400
        assert "Invalid state transition" in update_response.json()["detail"]

    @pytest.mark.asyncio()
    async def test_update_application_final_state(self, client, auth_headers, admin_headers):
        """Test: Cannot update application from final state"""
        # Create application
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
        }
        create_response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert create_response.status_code == 201
        application_id = create_response.json()["id"]

        # First, transition to a final state (PENDING -> VALIDATING -> APPROVED)
        # Note: Update endpoint requires admin permissions
        # Step 1: PENDING -> VALIDATING
        update_payload_1 = {"status": "VALIDATING"}
        await client.patch(
            f"/api/v1/applications/{application_id}",
            json=update_payload_1,
            headers=admin_headers
        )

        # Step 2: VALIDATING -> APPROVED
        update_payload_2 = {"status": "APPROVED"}
        await client.patch(
            f"/api/v1/applications/{application_id}",
            json=update_payload_2,
            headers=admin_headers
        )

        # Now try to change from APPROVED (final state) to PENDING (should fail)
        update_payload_3 = {"status": "PENDING"}
        update_response = await client.patch(
            f"/api/v1/applications/{application_id}",
            json=update_payload_3,
            headers=admin_headers
        )
        assert update_response.status_code == 400
        assert "Cannot change status from final state" in update_response.json()["detail"]

    @pytest.mark.asyncio()
    async def test_update_application_same_status(self, client, auth_headers, admin_headers):
        """Test: Updating to same status is allowed (no-op)"""
        # Create application
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
        }
        create_response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert create_response.status_code == 201
        application_id = create_response.json()["id"]

        # Update to same status (should be allowed)
        # Note: Update endpoint requires admin permissions
        update_payload = {"status": "PENDING"}
        update_response = await client.patch(
            f"/api/v1/applications/{application_id}",
            json=update_payload,
            headers=admin_headers
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "PENDING"
