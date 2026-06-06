import pytest

from src.models.batch_result import BatchResult

def test_success_result():
    result = BatchResult(success_count=5, failed_count=0, errors=[])
    assert result.success_count == 5
    assert result.failed_count == 0
    assert result.total == 5
    assert result.all_success

def test_partial_failure():
    result = BatchResult(success_count=3, failed_count=2, errors=["err1", "err2"])
    assert not result.all_success
    assert result.total == 5

def test_to_dict():
    result = BatchResult(success_count=5, failed_count=1, errors=["error details"])
    d = result.to_dict()
    assert d["success_count"] == 5
    assert d["failed_count"] == 1
    assert len(d["errors"]) == 1
