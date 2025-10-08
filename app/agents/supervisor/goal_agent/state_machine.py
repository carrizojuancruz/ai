"""State machine for goal status transitions."""

from typing import Optional

from .models import GoalStatus


class GoalStatusTransitionValidator:
    """Validates goal status transitions according to business rules."""

    # Define valid transitions based on the prompt rules
    VALID_TRANSITIONS = {
        GoalStatus.PENDING: [
            GoalStatus.IN_PROGRESS,
            GoalStatus.PAUSED,
            GoalStatus.OFF_TRACK,
            GoalStatus.DELETED
        ],
        GoalStatus.IN_PROGRESS: [
            GoalStatus.COMPLETED,
            GoalStatus.PAUSED,
            GoalStatus.OFF_TRACK,
            GoalStatus.ERROR,
            GoalStatus.DELETED
        ],
        GoalStatus.PAUSED: [
            GoalStatus.IN_PROGRESS,
            GoalStatus.OFF_TRACK,
            GoalStatus.DELETED
        ],
        GoalStatus.OFF_TRACK: [
            GoalStatus.IN_PROGRESS,
            GoalStatus.PAUSED,
            GoalStatus.DELETED
        ],
        GoalStatus.COMPLETED: [
            GoalStatus.PAUSED,
            GoalStatus.OFF_TRACK,
            GoalStatus.DELETED
        ],
        GoalStatus.ERROR: [
            GoalStatus.IN_PROGRESS,
            GoalStatus.PAUSED,
            GoalStatus.DELETED
        ],
        GoalStatus.DELETED: []  # Cannot transition from deleted
    }

    @classmethod
    def can_transition(
        cls,
        from_status: GoalStatus,
        to_status: GoalStatus
    ) -> tuple[bool, Optional[str]]:
        """Check if a status transition is valid.

        Args:
            from_status: Current goal status
            to_status: Desired goal status

        Returns:
            Tuple of (is_valid, error_message).
            If valid, error_message is None.

        """
        # Check if trying to transition to same status
        if from_status == to_status:
            return False, f"Goal is already in '{to_status.value}' status"

        # Check if transition is in valid transitions list
        valid_targets = cls.VALID_TRANSITIONS.get(from_status, [])
        if to_status not in valid_targets:
            available = [s.value for s in valid_targets]
            return False, (
                f"Cannot transition from '{from_status.value}' to '{to_status.value}'. "
                f"Valid transitions from '{from_status.value}' are: {', '.join(available)}"
            )

        return True, None

    @classmethod
    def get_valid_transitions(cls, from_status: GoalStatus) -> list[str]:
        """Get list of valid transition target statuses.

        Args:
            from_status: Current goal status

        Returns:
            List of valid status values as strings

        """
        return [s.value for s in cls.VALID_TRANSITIONS.get(from_status, [])]
