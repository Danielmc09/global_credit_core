"""State Machine for Application Status Transitions.

This module defines the valid state transitions for credit applications.
It ensures that applications can only transition between valid states according
to business rules.

State Machine Diagram:
    PENDING
        ├──> VALIDATING
        └──> CANCELLED (final)

    VALIDATING
        ├──> APPROVED (final)
        ├──> REJECTED (final)
        └──> UNDER_REVIEW

    UNDER_REVIEW
        ├──> APPROVED (final)
        └──> REJECTED (final)

    APPROVED (final) - No transitions allowed
    REJECTED (final) - No transitions allowed
    CANCELLED (final) - No transitions allowed
    COMPLETED (final) - No transitions allowed

Rules:
- Applications start in PENDING status
- PENDING can transition to VALIDATING (when processing starts) or CANCELLED (if cancelled)
- VALIDATING can transition to APPROVED, REJECTED, or UNDER_REVIEW (based on risk assessment)
- UNDER_REVIEW can transition to APPROVED or REJECTED (after manual review)
- Final states (APPROVED, REJECTED, CANCELLED, COMPLETED) cannot be changed
- No backward transitions are allowed (e.g., cannot go from VALIDATING back to PENDING)
"""


from ..models.application import ApplicationStatus

ALLOWED_TRANSITIONS: dict[ApplicationStatus, list[ApplicationStatus]] = {
    ApplicationStatus.PENDING: [
        ApplicationStatus.VALIDATING,
        ApplicationStatus.CANCELLED,
    ],
    ApplicationStatus.VALIDATING: [
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.UNDER_REVIEW,
    ],
    ApplicationStatus.UNDER_REVIEW: [
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
    ],
    ApplicationStatus.APPROVED: [],
    ApplicationStatus.REJECTED: [],
    ApplicationStatus.CANCELLED: [],
    ApplicationStatus.COMPLETED: [],
}

FINAL_STATES: list[ApplicationStatus] = [
    ApplicationStatus.APPROVED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.CANCELLED,
    ApplicationStatus.COMPLETED,
]


def validate_transition(
    old_status: ApplicationStatus,
    new_status: ApplicationStatus
) -> None:
    """Validate that a state transition is allowed.

    Args:
        old_status: Current application status
        new_status: Desired new application status

    Raises:
        ValueError: If the transition is not allowed
    """
    if old_status == new_status:
        return

    if old_status in FINAL_STATES:
        raise ValueError(
            f"Cannot change status from final state '{old_status.value}'. "
            f"Final states ({', '.join([s.value for s in FINAL_STATES])}) cannot be modified."
        )

    allowed_next_states = ALLOWED_TRANSITIONS.get(old_status)

    if allowed_next_states is None:
        raise ValueError(
            f"Unknown current status: '{old_status.value}'. "
            f"Cannot determine valid transitions."
        )

    if new_status not in allowed_next_states:
        valid_transitions_str = ', '.join([s.value for s in allowed_next_states])
        raise ValueError(
            f"Invalid state transition: '{old_status.value}' → '{new_status.value}'. "
            f"Valid transitions from '{old_status.value}' are: {valid_transitions_str or 'none (final state)'}"
        )


def is_final_state(status: ApplicationStatus) -> bool:
    """Check if a status is a final state (cannot be changed).

    Args:
        status: Application status to check

    Returns:
        True if status is final, False otherwise
    """
    return status in FINAL_STATES


def get_allowed_transitions(current_status: ApplicationStatus) -> list[ApplicationStatus]:
    """Get list of allowed transitions from a given status.

    Args:
        current_status: Current application status

    Returns:
        List of allowed next statuses
    """
    return ALLOWED_TRANSITIONS.get(current_status, [])
