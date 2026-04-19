import pytest

from src.domain.enums.request_status import RequestStatus
from src.domain.rules.transition_rules import validate_transition, validate_transition_requirements
from src.shared.errors import ConflictError, ValidationError


class TestValidateTransition:
    def test_submitted_to_triaged(self):
        validate_transition(RequestStatus.SUBMITTED, RequestStatus.TRIAGED)

    def test_triaged_to_assigned(self):
        validate_transition(RequestStatus.TRIAGED, RequestStatus.ASSIGNED)

    def test_submitted_to_assigned(self):
        validate_transition(RequestStatus.SUBMITTED, RequestStatus.ASSIGNED)

    def test_assigned_to_in_progress(self):
        validate_transition(RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS)

    def test_in_progress_to_resolved(self):
        validate_transition(RequestStatus.IN_PROGRESS, RequestStatus.RESOLVED)

    def test_submitted_to_cancelled(self):
        validate_transition(RequestStatus.SUBMITTED, RequestStatus.CANCELLED)

    def test_triaged_to_cancelled(self):
        validate_transition(RequestStatus.TRIAGED, RequestStatus.CANCELLED)

    def test_assigned_to_cancelled(self):
        validate_transition(RequestStatus.ASSIGNED, RequestStatus.CANCELLED)

    def test_in_progress_to_cancelled(self):
        validate_transition(RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED)

    def test_invalid_submitted_to_resolved(self):
        with pytest.raises(ConflictError):
            validate_transition(RequestStatus.SUBMITTED, RequestStatus.RESOLVED)

    def test_invalid_triaged_to_resolved(self):
        with pytest.raises(ConflictError):
            validate_transition(RequestStatus.TRIAGED, RequestStatus.RESOLVED)

    def test_terminal_resolved(self):
        with pytest.raises(ConflictError):
            validate_transition(RequestStatus.RESOLVED, RequestStatus.SUBMITTED)

    def test_terminal_cancelled(self):
        with pytest.raises(ConflictError):
            validate_transition(RequestStatus.CANCELLED, RequestStatus.SUBMITTED)

    def test_resolved_to_cancelled(self):
        with pytest.raises(ConflictError):
            validate_transition(RequestStatus.RESOLVED, RequestStatus.CANCELLED)


class TestValidateTransitionRequirements:
    def test_assigned_requires_responder_unit_id(self):
        with pytest.raises(ValidationError):
            validate_transition_requirements(RequestStatus.ASSIGNED, {})

    def test_assigned_with_responder_unit_id(self):
        validate_transition_requirements(RequestStatus.ASSIGNED, {"responderUnitId": "unit-001"})

    def test_cancelled_requires_reason(self):
        with pytest.raises(ValidationError):
            validate_transition_requirements(RequestStatus.CANCELLED, {})

    def test_cancelled_with_reason(self):
        validate_transition_requirements(RequestStatus.CANCELLED, {"reason": "Duplicate request"})

    def test_triaged_no_special_requirements(self):
        validate_transition_requirements(RequestStatus.TRIAGED, {})

    def test_in_progress_no_special_requirements(self):
        validate_transition_requirements(RequestStatus.IN_PROGRESS, {})

    def test_resolved_no_special_requirements(self):
        validate_transition_requirements(RequestStatus.RESOLVED, {})
