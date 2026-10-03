from testoracle.compare import holds, outcome_equal, same
from testoracle.generation import Assertion, parse
from testoracle.mutation import candidates, witnessed
from testoracle.sandbox import run

SOURCE = '''def clip(x: int, low: int, high: int) -> int:
    """Return x limited to [low, high]."""
    if x < low:
        return low
    if x > high:
        return high
    return x
'''


def test_parse_accepts_literal_assertions_only():
    text = """```python
assert clip(5, 0, 3) == 3
assert clip(-1, 0, 3) is 0
assert not clip(0, 0, 0)
assert clip(x, 0, 3) == 1
assert clip(1, 0, 3) == y
assert other(1) == 1
```"""
    result = parse(text, "clip")
    assert result["assertions"] == [Assertion([5, 0, 3], "eq", 3), Assertion([0, 0, 0], "falsy", None)]
    assert result["lines"] == 6 and result["rejected"] == 4


def test_predicates_are_evaluated_as_written():
    assert holds(Assertion([], "truthy", None), ("ok", 2))
    assert holds(Assertion([], "falsy", None), ("ok", []))
    assert not holds(Assertion([], "eq", True), ("ok", 2))
    assert not holds(Assertion([], "is", False), ("ok", 0))
    assert holds(Assertion([], "is", None), ("ok", None))
    assert not holds(Assertion([], "eq", 1), ("error", "ValueError"))


def test_parse_keeps_first_six():
    text = "\n".join(f"assert clip({i}, 0, 9) == {i}" for i in range(8))
    assert len(parse(text, "clip")["assertions"]) == 6
    assert len(parse(text, "clip", limit=None)["assertions"]) == 8


def test_same_uses_float_tolerance_and_types():
    assert same(0.1 + 0.2, 0.3)
    assert not same([1, 2], (1, 2))
    assert same(True, 1)
    assert outcome_equal(("error", "ValueError"), ("error", "ValueError"))
    assert not outcome_equal(("ok", 1), ("error", "ValueError"))


def test_sandbox_reports_errors_and_timeouts():
    source = "def f(x):\n    if x < 0:\n        while True:\n            pass\n    return 10 // x\n"
    outcomes = run(source, "f", [[2], [0], [-1]])
    assert outcomes[0] == ("ok", 5)
    assert outcomes[1] == ("error", "ZeroDivisionError")
    assert outcomes[2] == ("timeout", None)
    assert run(source, "f", [[-1], [5]]) == [("timeout", None), ("ok", 2)]
    assert run(source, "f", [[-1], [5]], stop_at_timeout=True) == [("timeout", None), ("timeout", None)]


def test_mutants_change_behaviour():
    task = {"task_id": "toy", "entry": "clip", "solution": SOURCE,
            "plus_inputs": [[-5, 0, 3], [0, 0, 3], [3, 0, 3], [9, 0, 3], [2, 0, 3]],
            "plus_outputs": [0, 0, 3, 3, 2]}
    all_mutants = candidates(SOURCE, "clip")
    kept = witnessed(task)
    assert 0 < len(kept) <= len(all_mutants)
    assert all("Return x limited" in m["source"] for m in kept)
    for mutant in kept:
        outcomes = run(mutant["source"], "clip", task["plus_inputs"])
        assert any(not outcome_equal(o, ("ok", e)) for o, e in zip(outcomes, task["plus_outputs"]))


def test_sandbox_keeps_outcomes_before_a_crash():
    source = "import os\ndef f(x):\n    if x == 0:\n        os._exit(1)\n    return x\n"
    assert run(source, "f", [[1], [2], [0], [3]]) == [("ok", 1), ("ok", 2), ("error", "WorkerCrash"), ("ok", 3)]


def test_contract_blocks_inputs_outside_the_task():
    from testoracle.contracts import CONTRACTS
    check = CONTRACTS["HumanEval/160"]
    assert check([["+", "*"], [1, 2, 3]])
    assert not check([['+ len("abc") +'], [1, 2]])
    source = "def g(ops, nums):\n    return eval(str(nums[0]) + ops[0] + str(nums[1]))\n"
    assert run(source, "g", [[['+ len("abc") +'], [1, 2]]], check=check) == [("error", "OutsideContract")]
