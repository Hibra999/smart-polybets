from core.schemas.precondition import PreconditionResult


def test_is_violation_only_for_mandatory_false():
    assert PreconditionResult(name="x", ok=False, severity="mandatory").is_violation is True
    assert PreconditionResult(name="x", ok=False, severity="advisory").is_violation is False
    assert PreconditionResult(name="x", ok=True, severity="mandatory").is_violation is False
    assert PreconditionResult(name="x", ok=None, severity="mandatory").is_violation is False


def test_frozen():
    import pytest
    r = PreconditionResult(name="x", ok=True, severity="mandatory")
    with pytest.raises(Exception):
        r.name = "y"
