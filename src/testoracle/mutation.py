"""First-order mutants of a reference solution, kept only when some HumanEval+ input tells them apart."""
import ast
import copy
import random

from .compare import outcome_equal
from .config import MAX_MUTANTS, SEED
from .sandbox import run

BINARY = {ast.Add: [ast.Sub], ast.Sub: [ast.Add], ast.Mult: [ast.FloorDiv, ast.Add], ast.Div: [ast.Mult],
          ast.FloorDiv: [ast.Div, ast.Mult], ast.Mod: [ast.FloorDiv], ast.Pow: [ast.Mult]}
COMPARE = {ast.Lt: [ast.LtE, ast.Gt], ast.LtE: [ast.Lt, ast.GtE], ast.Gt: [ast.GtE, ast.Lt],
           ast.GtE: [ast.Gt, ast.LtE], ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq], ast.In: [ast.NotIn],
           ast.NotIn: [ast.In], ast.Is: [ast.IsNot], ast.IsNot: [ast.Is]}
BOOLEAN = {ast.And: ast.Or, ast.Or: ast.And}


def _sites(function: ast.FunctionDef):
    """(node path, description, mutate) for every mutation site in the function body."""
    body = function.body[1:] if ast.get_docstring(function) else function.body
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, (ast.BinOp, ast.AugAssign)) and type(node.op) in BINARY:
                for new in BINARY[type(node.op)]:
                    yield node, f"{type(node.op).__name__}->{new.__name__}", lambda n, new=new: setattr(n, "op", new())
            elif isinstance(node, ast.Compare):
                for i, op in enumerate(node.ops):
                    for new in COMPARE.get(type(op), []):
                        def change(n, i=i, new=new):
                            n.ops[i] = new()
                        yield node, f"{type(op).__name__}->{new.__name__}", change
            elif isinstance(node, ast.BoolOp):
                new = BOOLEAN[type(node.op)]
                yield node, f"{type(node.op).__name__}->{new.__name__}", lambda n, new=new: setattr(n, "op", new())
            elif isinstance(node, ast.Constant) and type(node.value) is int:
                for delta in (1, -1):
                    yield node, f"const{delta:+d}", lambda n, d=delta: setattr(n, "value", n.value + d)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                yield node, "drop-not", None


class _Unwrap(ast.NodeTransformer):
    def __init__(self, target):
        self.target = target

    def generic_visit(self, node):
        super().generic_visit(node)
        return node.operand if node is self.target else node


def candidates(source: str, entry: str) -> list[dict]:
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == entry)
    out = []
    for index, (node, description, mutate) in enumerate(list(_sites(function))):
        clone = copy.deepcopy(tree)
        target = [n for n in ast.walk(clone)][[n for n in ast.walk(tree)].index(node)]
        if mutate is None:
            clone = _Unwrap(target).visit(clone)
        else:
            mutate(target)
        out.append({"site": index, "operator": description, "line": node.lineno,
                    "source": ast.unparse(ast.fix_missing_locations(clone))})
    return out


def witnessed(task: dict) -> list[dict]:
    reference = [("ok", value) for value in task["plus_outputs"]]
    seen, kept = set(), []
    for mutant in candidates(task["solution"], task["entry"]):
        outcomes = run(mutant["source"], task["entry"], task["plus_inputs"], stop_at_timeout=True)
        differs = [i for i, (o, r) in enumerate(zip(outcomes, reference)) if not outcome_equal(o, r)]
        if not differs:
            continue
        signature = repr(outcomes)
        if signature in seen:
            continue
        seen.add(signature)
        kept.append({**mutant, "witnesses": len(differs)})
    random.Random(f"{SEED}:{task['task_id']}").shuffle(kept)
    return kept[:MAX_MUTANTS]


def write() -> None:
    import json

    from .config import DATA
    from .tasks import load

    (DATA / "mutants.json").write_text(json.dumps({task["task_id"]: witnessed(task) for task in load()}))
