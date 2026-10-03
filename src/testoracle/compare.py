import math

from .config import ATOL


def same(actual, expected) -> bool:
    """Equality as in the HumanEval+ checker: exact, or approximate for floats (relative 1e-7, absolute 1e-6).

    This is a normalised comparison: an `==` assertion on floats judged correct here may fail as literal Python.
    """
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


def holds(assertion, outcome: tuple) -> bool:
    """Whether the assertion passes for this outcome of the call, with the predicate as written."""
    if outcome[0] != "ok":
        return False
    value = outcome[1]
    if assertion.kind == "truthy":
        return bool(value)
    if assertion.kind == "falsy":
        return not value
    if assertion.kind == "is":
        return value is assertion.expected
    return same(value, assertion.expected)
