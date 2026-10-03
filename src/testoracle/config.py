from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
CACHE = ROOT / ".cache"

SEED = 2026
MAX_MUTANTS = 15
N_ASSERTIONS = 6
CALL_TIMEOUT = 2.0
ATOL = 1e-6

MODELS = {
    "qwen-coder-7b": ("ollama", "qwen2.5-coder:7b"),
    "gemma3-4b": ("ollama", "gemma3:4b"),
    "deepseek-v3.2": ("openrouter", "deepseek/deepseek-v3.2"),
}
CONTEXTS = ("spec", "code", "buggy")
