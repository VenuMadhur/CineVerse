"""
Subscription State Machine.

Encodes the valid subscription lifecycle transitions and rejects any
transition not explicitly allowed. This is a pure, side-effect-free
class so it can be unit tested independently of the database.

Valid transitions (per spec):
    trial      -> active
    trial      -> cancelled
    active     -> past_due
    active     -> paused
    active     -> cancelled
    past_due   -> active
    past_due   -> cancelled
    paused     -> active
    paused     -> cancelled

Explicitly invalid examples:
    cancelled  -> active
    cancelled  -> trial
    trial      -> past_due
"""
from app.exceptions.custom_exceptions import InvalidStateTransitionException
from app.models.enums import SubscriptionStatus

# Adjacency list of the finite state machine.
_VALID_TRANSITIONS: dict[SubscriptionStatus, set[SubscriptionStatus]] = {
    SubscriptionStatus.TRIAL: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.ACTIVE: {
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.PAUSED,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.PAST_DUE: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.PAUSED: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.CANCELLED: set(),  # terminal state
}


class SubscriptionStateMachine:
    @staticmethod
    def can_transition(
        current: SubscriptionStatus, target: SubscriptionStatus
    ) -> bool:
        return target in _VALID_TRANSITIONS.get(current, set())

    @staticmethod
    def assert_valid_transition(
        current: SubscriptionStatus, target: SubscriptionStatus
    ) -> None:
        if not SubscriptionStateMachine.can_transition(current, target):
            raise InvalidStateTransitionException(current.value, target.value)

    @staticmethod
    def allowed_targets(current: SubscriptionStatus) -> set[SubscriptionStatus]:
        return _VALID_TRANSITIONS.get(current, set())
