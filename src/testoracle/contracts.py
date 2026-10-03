"""Input contracts for tasks whose reference solution evaluates its arguments as code."""


def _do_algebra(args) -> bool:
    if len(args) != 2:
        return False
    operator, operand = args
    return (isinstance(operator, list) and isinstance(operand, list) and len(operator) >= 1
            and len(operand) == len(operator) + 1
            and all(op in ("+", "-", "*", "//", "**") for op in operator)
            and all(type(x) is int and x >= 0 for x in operand))


CONTRACTS = {"HumanEval/160": _do_algebra}
