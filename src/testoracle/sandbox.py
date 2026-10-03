"""Runs trusted dataset code (reference solutions and their mutants) on literal inputs in a child process."""
import copy
import multiprocessing as mp
import signal

from .config import CALL_TIMEOUT

HEADER = "import math\nimport re\nimport string\nimport hashlib\nimport itertools\nimport collections\n" \
         "from typing import *\n"


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout


def _worker(source, entry, inputs, queue):
    signal.signal(signal.SIGALRM, _alarm)
    namespace = {}
    try:
        exec(HEADER + source, namespace)
    except Exception as error:
        queue.put([("error", type(error).__name__)] * len(inputs))
        return
    function = namespace[entry]
    outcomes = []
    for args in inputs:
        signal.setitimer(signal.ITIMER_REAL, CALL_TIMEOUT)
        try:
            outcomes.append(("ok", function(*copy.deepcopy(args))))
        except _Timeout:
            outcomes.append(("timeout", None))
        except BaseException as error:
            outcomes.append(("error", type(error).__name__))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        if outcomes[-1][0] == "timeout":
            outcomes += [("timeout", None)] * (len(inputs) - len(outcomes))
            break
    queue.put(_portable(outcomes))


def _portable(outcomes):
    """Values that cannot be sent between processes are reported as errors."""
    import pickle
    safe = []
    for outcome in outcomes:
        try:
            pickle.dumps(outcome)
            safe.append(outcome)
        except Exception:
            safe.append(("error", "Unpicklable"))
    return safe


def run(source: str, entry: str, inputs: list[list]) -> list[tuple]:
    """Outcome per input: ("ok", value), ("error", exception name) or ("timeout", None)."""
    if not inputs:
        return []
    context = mp.get_context("fork")
    queue = context.Queue()
    process = context.Process(target=_worker, args=(source, entry, inputs, queue))
    process.start()
    try:
        outcomes = queue.get(timeout=CALL_TIMEOUT * len(inputs) + 10)
    except Exception:
        outcomes = [("timeout", None)] * len(inputs)
    process.join(1)
    if process.is_alive():
        process.kill()
    return outcomes
