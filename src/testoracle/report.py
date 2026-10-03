"""Summary tables and figure from results/generations.jsonl and results/scores.jsonl."""
import json
from collections import defaultdict

import matplotlib
import numpy as np
from scipy.stats import binomtest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import CONTEXTS, MODELS, RESULTS, SEED
from .experiment import _read

BOOTSTRAP = 2000


def _mean_ci(values, seed=SEED):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(BOOTSTRAP, len(values)))].mean(axis=1)
    return float(values.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _mcnemar(a, b):
    only_a, only_b = int(np.sum(a & ~b)), int(np.sum(~a & b))
    return 1.0 if only_a + only_b == 0 else binomtest(only_a, only_a + only_b, 0.5).pvalue


def _suite_rows():
    rows = defaultdict(dict)
    for s in _read(RESULTS / "scores.jsonl"):
        rows[(s["model"], s["context"])][s["task_id"]] = s
    return rows


def _detection(suite, measure):
    return float(np.mean([k[measure] for k in suite["kills"]]))


def oracle_table(rows) -> dict:
    """Pooled assertion shares, share of fully correct suites and mean per-function mutation detection."""
    out = {}
    for (model, context), suites in rows.items():
        values = list(suites.values())
        n = sum(s["n"] for s in values)
        with_mutants = [s for s in values if s["kills"]]
        filtered = [_detection(s, "filtered") for s in with_mutants]
        corrected = [_detection(s, "corrected") for s in with_mutants]
        out[f"{model}|{context}"] = {
            "suites": len(values), "assertions": n, "per_suite": n / len(values),
            "empty_suites": sum(s["n"] == 0 for s in values),
            "non_executable": (n - sum(s["valid"] for s in values)) / n,
            "wrong_oracle": (sum(s["valid"] for s in values) - sum(s["correct"] for s in values)) / n,
            "correct": sum(s["correct"] for s in values) / n,
            "all_correct_suites": sum(s["n"] > 0 and s["correct"] == s["n"] for s in values) / len(values),
            "kill_filtered": _mean_ci(filtered), "kill_corrected": _mean_ci(corrected),
            "oracle_loss": _mean_ci([c - f for c, f in zip(corrected, filtered)]),
            "tasks_with_mutants": len(with_mutants),
        }
    return out


def human_comparison(rows) -> dict:
    """Filtered detection of every model and context on the functions whose original tests could be parsed."""
    base = {t: s for t, s in rows[("base", "human")].items() if s["n"] > 0 and s["kills"]}
    out = {"functions": len(base), "human": _mean_ci([_detection(s, "filtered") for s in base.values()])}
    for (model, context), suites in rows.items():
        if model == "base":
            continue
        common = [t for t in base if t in suites]
        out[f"{model}|{context}"] = {"functions": len(common),
                                     "model": _mean_ci([_detection(suites[t], "filtered") for t in common]),
                                     "difference": _mean_ci([_detection(suites[t], "filtered")
                                                             - _detection(base[t], "filtered") for t in common])}
    return out


def _correct_share(suite):
    return suite["correct"] / suite["n"] if suite["n"] else 0.0


def context_contrasts(rows) -> dict:
    """Paired per-function differences in the share of correct assertions and in filtered detection."""
    out = {}
    for model in MODELS:
        for a, b in (("spec", "code"), ("code", "buggy")):
            if (model, a) not in rows or (model, b) not in rows:
                continue
            tasks = sorted(set(rows[(model, a)]) & set(rows[(model, b)]))
            sa, sb = rows[(model, a)], rows[(model, b)]
            out[f"{model}|{b}-{a}|correct_share"] = _mean_ci([_correct_share(sb[t]) - _correct_share(sa[t])
                                                              for t in tasks]) + (len(tasks),)
            with_mutants = [t for t in tasks if sa[t]["kills"]]
            out[f"{model}|{b}-{a}|kill_filtered"] = _mean_ci([_detection(sb[t], "filtered")
                                                              - _detection(sa[t], "filtered")
                                                              for t in with_mutants]) + (len(with_mutants),)
    return out


def buggy_analysis(rows) -> dict:
    """Detection and encoding of the bug in the implementation shown to the test writer, from the stored scores.

    The same measures are computed for the spec suite of the same model and function against the same mutant: its
    agreement with the mutant shows how often expected values coincide with the mutant's behaviour without the
    model having seen it.
    """
    out = {}
    for model in MODELS:
        buggy_rows, spec_rows = rows.get((model, "buggy"), {}), rows.get((model, "spec"), {})
        tasks = sorted(t for t in buggy_rows if t in spec_rows)
        if not tasks:
            continue
        counts = {ctx: defaultdict(int) for ctx in ("buggy", "spec")}
        detected = {"buggy": [], "spec": []}
        for task_id in tasks:
            site = buggy_rows[task_id]["mutant_site"]
            for ctx, suite in (("buggy", buggy_rows[task_id]), ("spec", spec_rows[task_id])):
                kill = next(k for k in suite["kills"] if k["site"] == site)
                fails, differs = set(kill["fails"]), set(kill["differs"])
                c = counts[ctx]
                for i in range(suite["n"]):
                    on_reference, on_mutant = suite["assertion_correct"][i], i not in fails
                    c["assertions"] += 1
                    if i in differs:
                        c["revealing"] += 1
                        c["encoded"] += on_mutant and not on_reference
                    if not on_mutant:
                        c["failing"] += 1
                        c["failing_correct"] += on_reference
                        c["failing_non_executable"] += not suite["assertion_valid"][i]
                detected[ctx].append(kill["filtered"])
                c["raw_failure"] += kill["raw"]
        a, b = np.array(detected["buggy"]), np.array(detected["spec"])
        result = {"tasks": len(a), "detected_buggy": float(a.mean()), "detected_spec": float(b.mean()),
                  "p_mcnemar": _mcnemar(a, b)}
        for ctx, c in counts.items():
            result[ctx] = {**c, "encoded_share": c["encoded"] / c["revealing"],
                           "failing_correct_share": c["failing_correct"] / c["failing"],
                           "failing_non_executable_share": c["failing_non_executable"] / c["failing"],
                           "raw_failure_share": c["raw_failure"] / len(a)}
        out[model] = result
    return out


def report() -> dict:
    rows = _suite_rows()
    out = {"oracles": oracle_table(rows), "human": human_comparison(rows), "contexts": context_contrasts(rows),
           "buggy": buggy_analysis(rows)}
    (RESULTS / "summary.json").write_text(json.dumps(out, indent=1))
    _figure(out)
    return out


def _figure(out):
    labels = {"qwen-coder-7b": "Qwen2.5-Coder-7B", "gemma3-4b": "Gemma3-4B", "deepseek-v3.2": "DeepSeek-V3.2"}
    rows = [(f"{labels[m]}, {c}", out["oracles"][f"{m}|{c}"]) for m in MODELS for c in CONTEXTS
            if f"{m}|{c}" in out["oracles"]]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    y = np.arange(len(rows))[::-1]
    correct = np.array([100 * r["correct"] for _, r in rows])
    wrong = np.array([100 * r["wrong_oracle"] for _, r in rows])
    other = np.array([100 * r["non_executable"] for _, r in rows])
    ax.barh(y, correct, color="0.85", edgecolor="black", linewidth=0.6, label="correct")
    ax.barh(y, wrong, left=correct, color="0.35", edgecolor="black", linewidth=0.6, label="wrong expected value")
    ax.barh(y, other, left=correct + wrong, color="white", edgecolor="black", linewidth=0.6, hatch="////",
            label="non-executable input")
    for yi, c, w in zip(y, correct, wrong):
        ax.text(c + w / 2, yi, f"{w:.1f}", ha="center", va="center", color="white", fontsize=10)
    ax.set_yticks(y, [name for name, _ in rows], fontsize=10)
    ax.set_xlim(70, 100)
    ax.set_xlabel("Share of assertions, %", fontsize=10)
    ax.tick_params(axis="x", labelsize=10)
    ax.legend(fontsize=9, loc="lower left", frameon=False, ncol=3, bbox_to_anchor=(-0.45, 1.0))
    fig.tight_layout()
    fig.savefig(RESULTS / "assertions.png", dpi=300)
    plt.close(fig)
