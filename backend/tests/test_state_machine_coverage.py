"""
Additional tests for state machine to improve coverage.

These tests focus on all state transitions and edge cases.
"""

import pytest

from app.core.state_machine import (
    get_allowed_transitions,
    is_final_state,
    validate_transition,
)
from app.models.application import ApplicationStatus


class TestStateMachineTransitions:
    """Test all valid state transitions"""

    def test_pending_to_validating(self):
        """Test PENDING -> VALIDATING transition"""
        validate_transition(ApplicationStatus.PENDING, ApplicationStatus.VALIDATING)

    def test_pending_to_cancelled(self):
        """Test PENDING -> CANCELLED transition"""
        validate_transition(ApplicationStatus.PENDING, ApplicationStatus.CANCELLED)

    def test_validating_to_approved(self):
        """Test VALIDATING -> APPROVED transition"""
        validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.APPROVED)

    def test_validating_to_rejected(self):
        """Test VALIDATING -> REJECTED transition"""
        validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.REJECTED)

    def test_validating_to_under_review(self):
        """Test VALIDATING -> UNDER_REVIEW transition"""
        validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.UNDER_REVIEW)

    def test_under_review_to_approved(self):
        """Test UNDER_REVIEW -> APPROVED transition"""
        validate_transition(ApplicationStatus.UNDER_REVIEW, ApplicationStatus.APPROVED)

    def test_under_review_to_rejected(self):
        """Test UNDER_REVIEW -> REJECTED transition"""
        validate_transition(ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REJECTED)


class TestStateMachineInvalidTransitions:
    """Test invalid state transitions"""

    def test_pending_to_approved_invalid(self):
        """Test PENDING -> APPROVED (invalid - must go through VALIDATING)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.PENDING, ApplicationStatus.APPROVED)

        assert "Invalid state transition" in str(exc_info.value)

    def test_pending_to_rejected_invalid(self):
        """Test PENDING -> REJECTED (invalid)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.PENDING, ApplicationStatus.REJECTED)

        assert "Invalid state transition" in str(exc_info.value)

    def test_validating_to_pending_invalid(self):
        """Test VALIDATING -> PENDING (invalid - no backward transitions)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.VALIDATING, ApplicationStatus.PENDING)

        assert "Invalid state transition" in str(exc_info.value)

    def test_approved_to_pending_invalid(self):
        """Test APPROVED -> PENDING (invalid - final state)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.APPROVED, ApplicationStatus.PENDING)

        assert "Cannot change status from final state" in str(exc_info.value)

    def test_rejected_to_approved_invalid(self):
        """Test REJECTED -> APPROVED (invalid - final state)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.REJECTED, ApplicationStatus.APPROVED)

        assert "Cannot change status from final state" in str(exc_info.value)

    def test_cancelled_to_validating_invalid(self):
        """Test CANCELLED -> VALIDATING (invalid - final state)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.CANCELLED, ApplicationStatus.VALIDATING)

        assert "Cannot change status from final state" in str(exc_info.value)

    def test_completed_to_approved_invalid(self):
        """Test COMPLETED -> APPROVED (invalid - final state)"""
        with pytest.raises(ValueError) as exc_info:
            validate_transition(ApplicationStatus.COMPLETED, ApplicationStatus.APPROVED)

        assert "Cannot change status from final state" in str(exc_info.value)


class TestStateMachineEdgeCases:
    """Test edge cases and utility functions"""

    def test_same_status_transition(self):
        """Test transitioning to the same status (no-op)"""
        # Should not raise an exception
        validate_transition(ApplicationStatus.PENDING, ApplicationStatus.PENDING)
        validate_transition(ApplicationStatus.APPROVED, ApplicationStatus.APPROVED)

    def test_is_final_state_approved(self):
        """Test is_final_state for APPROVED"""
        assert is_final_state(ApplicationStatus.APPROVED) is True

    def test_is_final_state_rejected(self):
        """Test is_final_state for REJECTED"""
        assert is_final_state(ApplicationStatus.REJECTED) is True

    def test_is_final_state_cancelled(self):
        """Test is_final_state for CANCELLED"""
        assert is_final_state(ApplicationStatus.CANCELLED) is True

    def test_is_final_state_completed(self):
        """Test is_final_state for COMPLETED"""
        assert is_final_state(ApplicationStatus.COMPLETED) is True

    def test_is_final_state_pending(self):
        """Test is_final_state for PENDING (not final)"""
        assert is_final_state(ApplicationStatus.PENDING) is False

    def test_is_final_state_validating(self):
        """Test is_final_state for VALIDATING (not final)"""
        assert is_final_state(ApplicationStatus.VALIDATING) is False

    def test_is_final_state_under_review(self):
        """Test is_final_state for UNDER_REVIEW (not final)"""
        assert is_final_state(ApplicationStatus.UNDER_REVIEW) is False

    def test_get_allowed_transitions_pending(self):
        """Test get_allowed_transitions for PENDING"""
        transitions = get_allowed_transitions(ApplicationStatus.PENDING)
        assert ApplicationStatus.VALIDATING in transitions
        assert ApplicationStatus.CANCELLED in transitions
        assert len(transitions) == 2

    def test_get_allowed_transitions_validating(self):
        """Test get_allowed_transitions for VALIDATING"""
        transitions = get_allowed_transitions(ApplicationStatus.VALIDATING)
        assert ApplicationStatus.APPROVED in transitions
        assert ApplicationStatus.REJECTED in transitions
        assert ApplicationStatus.UNDER_REVIEW in transitions
        assert len(transitions) == 3

    def test_get_allowed_transitions_under_review(self):
        """Test get_allowed_transitions for UNDER_REVIEW"""
        transitions = get_allowed_transitions(ApplicationStatus.UNDER_REVIEW)
        assert ApplicationStatus.APPROVED in transitions
        assert ApplicationStatus.REJECTED in transitions
        assert len(transitions) == 2

    def test_get_allowed_transitions_approved(self):
        """Test get_allowed_transitions for APPROVED (final state)"""
        transitions = get_allowed_transitions(ApplicationStatus.APPROVED)
        assert transitions == []

    def test_get_allowed_transitions_rejected(self):
        """Test get_allowed_transitions for REJECTED (final state)"""
        transitions = get_allowed_transitions(ApplicationStatus.REJECTED)
        assert transitions == []

    def test_get_allowed_transitions_cancelled(self):
        """Test get_allowed_transitions for CANCELLED (final state)"""
        transitions = get_allowed_transitions(ApplicationStatus.CANCELLED)
        assert transitions == []

    def test_get_allowed_transitions_completed(self):
        """Test get_allowed_transitions for COMPLETED (final state)"""
        transitions = get_allowed_transitions(ApplicationStatus.COMPLETED)
        assert transitions == []

