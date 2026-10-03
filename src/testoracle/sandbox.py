"""Runs trusted dataset code (reference solutions and their mutants) on literal inputs in child processes."""
import copy
import multiprocessing as mp
import pickle
import signal

from .config import CALL_TIMEOUT

HEADER = "import math\nimport re\nimport string\nimport hashlib\nimport itertools\nimport collections\n" \
         "from typing import *\n"


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout


def _portable(outcome):
    """Values that cannot be sent between processes are reported as errors."""
    try:
        pickle.dumps(outcome)
        return outcome
    except Exception:
        return ("error", "Unpicklable")


def _worker(source, entry, inputs, results, check):
    signal.signal(signal.SIGALRM, _alarm)
    namespace = {}
    try:
        exec(HEADER + source, namespace)
    except Exception as error:
        for _ in inputs:
            results.send(("error", type(error).__name__))
        return
    function = namespace[entry]
    for args in inputs:
        if check is not None and not check(args):
            results.send(("error", "OutsideContract"))
            continue
        signal.setitimer(signal.ITIMER_REAL, CALL_TIMEOUT)
        try:
            outcome = ("ok", function(*copy.deepcopy(args)))
        except _Timeout:
            outcome = ("timeout", None)
        except BaseException as error:
            outcome = ("error", type(error).__name__)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        results.send(_portable(outcome))


def run(source: str, entry: str, inputs: list[list], stop_at_timeout: bool = False, check=None) -> list[tuple]:
    """Outcome per input: ("ok", value), ("error", exception name) or ("timeout", None).

    Each outcome is written to a pipe as soon as it is known, so outcomes already sent survive a crash of the child.
    If the child dies or stops answering, the current input is recorded as a crash or a timeout and a new child
    continues with the remaining inputs. With `stop_at_timeout`, the first timeout ends the run and the remaining
    inputs are recorded as timeouts (used to screen mutants on many inputs). `check` rejects inputs outside the
    task's contract before they reach the code.
    """
    context = mp.get_context("fork")
    outcomes = []
    while len(outcomes) < len(inputs):
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_worker, args=(source, entry, inputs[len(outcomes):], sender, check))
        process.start()
        sender.close()
        while len(outcomes) < len(inputs):
            if not receiver.poll(CALL_TIMEOUT + 5):
                outcomes.append(("timeout", None) if process.is_alive() else ("error", "WorkerCrash"))
                break
            try:
                outcomes.append(receiver.recv())
            except EOFError:
                outcomes.append(("error", "WorkerCrash"))
                break
            if stop_at_timeout and outcomes[-1][0] == "timeout":
                break
        process.kill()
        process.join()
        receiver.close()
        if stop_at_timeout and outcomes and outcomes[-1][0] == "timeout":
            outcomes += [("timeout", None)] * (len(inputs) - len(outcomes))
    return outcomes
