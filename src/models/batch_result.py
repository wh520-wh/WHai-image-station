from __future__ import annotations


class BatchResult:
    def __init__(self, success_count: int, failed_count: int, errors: list[str]):
        self.success_count = success_count
        self.failed_count = failed_count
        self.errors = errors

    @property
    def total(self) -> int:
        return self.success_count + self.failed_count

    @property
    def all_success(self) -> bool:
        return self.failed_count == 0

    def to_dict(self) -> dict:
        return {
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "total": self.total,
            "all_success": self.all_success,
            "errors": self.errors,
        }
