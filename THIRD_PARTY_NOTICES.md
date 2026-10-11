# Third-party data

`data/tasks.json` holds, for the 157 eligible tasks, the prompt, entry point, reference solution, HumanEval+ inputs
with their reference outputs and the original HumanEval test assertions; `data/mutants.json` holds mutants of those
reference solutions; `data/excluded_tasks.json` lists the tasks left out. The prompts in `results/generations.jsonl`
contain the same signatures, docstrings and solutions.

- HumanEval+ (https://huggingface.co/datasets/evalplus/humanevalplus), EvalPlus, under the Apache License,
  Version 2.0 (`LICENSES/Apache-2.0.txt`).
- HumanEval (https://github.com/openai/human-eval), MIT licence, Copyright (c) OpenAI (`LICENSES/MIT-HumanEval.txt`).

The MIT licence of this repository covers the code.
