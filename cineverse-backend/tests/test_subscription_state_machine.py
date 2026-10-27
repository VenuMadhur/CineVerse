"""
Unit tests for the subscription state machine (pure logic, no DB).
"""
import pytest

from app.exceptions.custom_exceptions import InvalidStateTransitionException
from app.models.enums import SubscriptionStatus
from app.services.subscription_state_machine import SubscriptionStateMachine


class TestValidTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            (SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE),
            (SubscriptionStatus.TRIAL, SubscriptionStatus.CANCELLED),
            (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE),
            (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED),
            (SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED),
            (SubscriptionStatus.PAST_DUE, SubscriptionStatus.ACTIVE),
            (SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELLED),
            (SubscriptionStatus.PAUSED, SubscriptionStatus.ACTIVE),
            (SubscriptionStatus.PAUSED, SubscriptionStatus.CANCELLED),
        ],
    )
    def test_allowed_transition_does_not_raise(self, current, target):
        SubscriptionStateMachine.assert_valid_transition(current, target)
        assert SubscriptionStateMachine.can_transition(current, target) is True


class TestInvalidTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            (SubscriptionStatus.CANCELLED, SubscriptionStatus.ACTIVE),
            (SubscriptionStatus.CANCELLED, SubscriptionStatus.TRIAL),
            (SubscriptionStatus.TRIAL, SubscriptionStatus.PAST_DUE),
            (SubscriptionStatus.TRIAL, SubscriptionStatus.PAUSED),
            (SubscriptionStatus.PAST_DUE, SubscriptionStatus.TRIAL),
        ],
    )
    def test_disallowed_transition_raises(self, current, target):
        assert SubscriptionStateMachine.can_transition(current, target) is False
        with pytest.raises(InvalidStateTransitionException):
            SubscriptionStateMachine.assert_valid_transition(current, target)


def test_cancelled_is_terminal():
    assert SubscriptionStateMachine.allowed_targets(SubscriptionStatus.CANCELLED) == set()
