"""Generates test suites for every task, model and context, then scores them against references and mutants."""
import json
import os

from .compare import holds, outcome_equal
from .config import CONTEXTS, DATA, MODELS, RESULTS
from .generation import build_prompt, complete, parse
from .sandbox import run
from .tasks import load

GENERATIONS = RESULTS / "generations.jsonl"


def _read(path):
    return [json.loads(line) for line in path.open()] if path.exists() else []


def mutants() -> dict:
    return json.loads((DATA / "mutants.json").read_text())


def shown_code(task, context, task_mutants):
    if context == "spec":
        return None, None
    if context == "code":
        return task["solution"], None
    if not task_mutants:
        return None, None
    return task_mutants[0]["source"], task_mutants[0]["site"]


def generate(model_names) -> None:
    tasks, all_mutants = load(), mutants()
    done = {(g["model"], g["task_id"], g["context"]) for g in _read(GENERATIONS)}
    key = os.environ.get("OPENROUTER_API_KEY")
    RESULTS.mkdir(exist_ok=True)
    for name in model_names:
        backend, model = MODELS[name]
        for context in CONTEXTS:
            for task in tasks:
                code, site = shown_code(task, context, all_mutants[task["task_id"]])
                if (name, task["task_id"], context) in done or (context != "spec" and code is None):
                    continue
                reply = complete(backend, model, build_prompt(task, context, code), key)
                row = {"model": name, "task_id": task["task_id"], "context": context, "mutant_site": site, **reply}
                with GENERATIONS.open("a") as handle:
                    handle.write(json.dumps(row) + "\n")


def score_suite(task, task_mutants, assertions) -> dict:
    inputs = [a.args for a in assertions]
    reference = run(task["solution"], task["entry"], inputs)
    valid = [r[0] == "ok" for r in reference]
    correct = [holds(a, r) for a, r in zip(assertions, reference)]
    kills = []
    for mutant in task_mutants:
        outcomes = run(mutant["source"], task["entry"], inputs)
        filtered = any(c and not holds(a, o) for c, a, o in zip(correct, assertions, outcomes))
        corrected = any(v and not outcome_equal(o, r) for v, o, r in zip(valid, outcomes, reference))
        raw = any(not holds(a, o) for a, o in zip(assertions, outcomes))
        kills.append({"site": mutant["site"], "filtered": filtered, "corrected": corrected, "raw": raw})
    return {"n": len(assertions), "valid": sum(valid), "correct": sum(correct), "kills": kills}


def score() -> None:
    tasks = {t["task_id"]: t for t in load()}
    all_mutants = mutants()
    out = RESULTS / "scores.jsonl"
    done = {(s["model"], s["task_id"], s["context"]) for s in _read(out)}
    rows = []
    for task in tasks.values():
        if (("base", task["task_id"], "human")) not in done:
            base = parse("\n".join(task["base_tests"]), task["entry"], limit=None)["assertions"]
            rows.append({"model": "base", "task_id": task["task_id"], "context": "human",
                         **score_suite(task, all_mutants[task["task_id"]], base)})
    for g in _read(GENERATIONS):
        if (g["model"], g["task_id"], g["context"]) in done:
            continue
        task = tasks[g["task_id"]]
        parsed = parse(g["text"], task["entry"])
        rows.append({"model": g["model"], "task_id": g["task_id"], "context": g["context"],
                     "mutant_site": g["mutant_site"], "lines": parsed["lines"], "rejected": parsed["rejected"],
                     **score_suite(task, all_mutants[task["task_id"]], parsed["assertions"])})
    with out.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
