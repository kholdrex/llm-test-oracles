"""Asking a model for literal test assertions and parsing them."""
import ast
import json
import re
import time
import urllib.request
from typing import NamedTuple

from .config import N_ASSERTIONS

OLLAMA = "http://localhost:11434/api/chat"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"

INSTRUCTION = (
    "Write exactly {n} test assertions for the Python function below. Put each assertion on its own line in the "
    "form\nassert {entry}(<arguments>) == <expected value>\nUse only literal values (numbers, strings, lists, "
    "tuples, dictionaries, booleans, None) for arguments and expected values. Choose inputs that are likely to "
    "reveal bugs, including edge cases. Reply with the assertions only, inside one ```python code block."
)
CONTEXT = {
    "spec": "The function's signature and docstring:",
    "code": "The function's signature, docstring and implementation:",
    "buggy": "The function's signature, docstring and implementation:",
}


def build_prompt(task: dict, context: str, code: str | None) -> str:
    shown = task["prompt"] if context == "spec" else code
    return (INSTRUCTION.format(n=N_ASSERTIONS, entry=task["entry"]) + "\n\n" + CONTEXT[context]
            + "\n```python\n" + shown.strip("\n") + "\n```")


def complete(backend: str, model: str, prompt: str, key: str | None = None) -> dict:
    if backend == "ollama":
        body = {"model": model, "stream": False, "keep_alive": "30m",
                "options": {"temperature": 0, "num_predict": 800, "num_ctx": 4096, "seed": 0},
                "messages": [{"role": "user", "content": prompt}]}
        request = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    else:
        body = {"model": model, "temperature": 0, "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]}
        request = urllib.request.Request(OPENROUTER, json.dumps(body).encode(),
                                         {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    began = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        reply = json.load(response)
    seconds = time.perf_counter() - began
    if backend == "ollama":
        return {"text": reply["message"]["content"], "seconds": seconds,
                "input_tokens": reply.get("prompt_eval_count"), "output_tokens": reply.get("eval_count")}
    usage = reply.get("usage", {})
    return {"text": reply["choices"][0]["message"]["content"], "seconds": seconds,
            "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
            "cost": usage.get("cost"), "provider": reply.get("provider")}


FENCE = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)


def _literal(node):
    return ast.literal_eval(node)


def _call_args(node, entry):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == entry \
            and not node.keywords:
        return [_literal(a) for a in node.args]
    raise ValueError("not a call of the function under test")


class Assertion(NamedTuple):
    args: list
    kind: str
    expected: object


def parse_assertion(node: ast.Assert, entry: str) -> Assertion:
    """The call arguments, the predicate and the expected value; raises ValueError for unsupported forms."""
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Eq, ast.Is)):
        kind = "eq" if isinstance(test.ops[0], ast.Eq) else "is"
        return Assertion(_call_args(test.left, entry), kind, _literal(test.comparators[0]))
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return Assertion(_call_args(test.operand, entry), "falsy", None)
    return Assertion(_call_args(test, entry), "truthy", None)


def parse(text: str, entry: str, limit: int | None = N_ASSERTIONS) -> dict:
    blocks = FENCE.findall(text)
    code = blocks[0] if blocks else text
    lines = [line for line in code.splitlines() if line.strip().startswith("assert")]
    parsed, rejected = [], 0
    for line in lines:
        try:
            node = ast.parse(line.strip()).body[0]
            parsed.append(parse_assertion(node, entry))
        except (SyntaxError, ValueError, TypeError, IndexError, MemoryError, RecursionError):
            rejected += 1
    return {"assertions": parsed[:limit], "lines": len(lines), "rejected": rejected}
