"""HumanEval+ tasks whose behaviour can be checked by literal input/output pairs."""
import ast
import json

from datasets import load_dataset

from .compare import outcome_equal
from .config import DATA
from .sandbox import run


def _literal_assignment(tree: ast.AST, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def _standard_checker(test: str) -> bool:
    return "for i, (inp, exp) in enumerate(zip(inputs, results)):" in test and \
        "assertion(candidate(*inp), exp, " in test


def _base_tests(test: str, entry: str) -> list[str]:
    tree = ast.parse(test)
    check = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check")
    return [ast.unparse(n).replace("candidate", entry) for n in check.body if isinstance(n, ast.Assert)]


def build() -> list[dict]:
    plus = load_dataset("evalplus/humanevalplus")["test"]
    base = {row["task_id"]: row for row in load_dataset("openai/openai_humaneval")["test"]}
    tasks, excluded = [], {}
    for row in plus:
        task_id, entry = row["task_id"], row["entry_point"]
        source = row["prompt"] + row["canonical_solution"]
        if not _standard_checker(row["test"]):
            excluded[task_id] = "custom checker"
            continue
        try:
            inputs = _literal_assignment(ast.parse(row["test"]), "inputs")
        except (ValueError, SyntaxError):
            inputs = None
        if not inputs:
            excluded[task_id] = "inputs not literal"
            continue
        first, second = run(source, entry, inputs), run(source, entry, inputs)
        if any(o[0] != "ok" for o in first):
            excluded[task_id] = "reference fails on plus inputs"
            continue
        if not all(outcome_equal(a, b) for a, b in zip(first, second)):
            excluded[task_id] = "non-deterministic"
            continue
        try:
            outputs = [ast.literal_eval(repr(o[1])) for o in first]
        except (ValueError, SyntaxError):
            excluded[task_id] = "outputs not literal"
            continue
        tasks.append({"task_id": task_id, "entry": entry, "prompt": row["prompt"].strip("\n"),
                      "solution": source, "plus_inputs": inputs, "plus_outputs": outputs,
                      "base_tests": _base_tests(base[task_id]["test"], entry)})
    return tasks, excluded


LITERAL_FIELDS = ("plus_inputs", "plus_outputs")


def write() -> None:
    """Literal inputs and outputs are stored as Python source, so tuples and sets keep their types."""
    tasks, excluded = build()
    DATA.mkdir(exist_ok=True)
    stored = [{**t, **{f: repr(t[f]) for f in LITERAL_FIELDS}} for t in tasks]
    (DATA / "tasks.json").write_text(json.dumps(stored))
    (DATA / "excluded_tasks.json").write_text(json.dumps(excluded, indent=1))


def load() -> list[dict]:
    tasks = json.loads((DATA / "tasks.json").read_text())
    return [{**t, **{f: ast.literal_eval(t[f]) for f in LITERAL_FIELDS}} for t in tasks]
