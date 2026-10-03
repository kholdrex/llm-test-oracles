import math

from .config import ATOL


def same(actual, expected) -> bool:
    """Equality as in the HumanEval+ checker: exact, or within an absolute tolerance for floats."""
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if isinstance(actual, float) or isinstance(expected, float):
            return math.isclose(actual, expected, rel_tol=1e-7, abs_tol=ATOL) or actual == expected
        return actual == expected
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return type(actual) is type(expected) and len(actual) == len(expected) and all(
            same(a, e) for a, e in zip(actual, expected))
    return actual == expected


def outcome_equal(a: tuple, b: tuple) -> bool:
    if a[0] != b[0]:
        return False
    return same(a[1], b[1]) if a[0] == "ok" else a[1] == b[1]
