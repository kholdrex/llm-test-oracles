# Protocol

Fixed before test generation. Deviations are listed in CHANGELOG.md.

## Question

When a language model writes unit tests for a function, how much of the tests' fault-detection loss is due to the
chosen inputs and how much to wrong expected values (oracles)? Does showing the implementation help, and does a test
writer shown a buggy implementation still detect that bug?

## Tasks and faults

- HumanEval+ (evalplus/humanevalplus): tasks whose checker compares `candidate(*inp)` with a literal expected value
  (157 of 164; 7 with custom checkers excluded). The reference solution is run on all HumanEval+ inputs.
- Mutants: every first-order mutant of the entry function (arithmetic, comparison and boolean operator replacement,
  integer constant ±1, removal of `not`). A mutant is kept if at least one HumanEval+ input gives a different outcome
  (value, exception type or timeout) from the reference; mutants with identical outcome vectors are merged; at most
  15 per task, chosen by a seeded shuffle. Tasks without such mutants enter only the oracle analysis.

## Generation

- Models: qwen2.5-coder:7b and gemma3:4b (local, Ollama), deepseek/deepseek-v3.2 (OpenRouter). Temperature 0,
  at most 800 output tokens, one fixed instruction asking for exactly six `assert f(args) == expected` lines with
  literal values.
- Contexts: `spec` (signature and docstring), `code` (plus the reference implementation), `buggy` (plus the first
  kept mutant of the task instead of the reference).
- Parsing: only assertions of the forms `f(args) == v`, `f(args) is v`, `f(args)`, `not f(args)` with literal
  arguments are accepted; the first six are used. Generated text is never executed.

## Measures (per suite)

- Assertion classes: rejected by the parser; invalid input (reference raises or times out); wrong oracle (reference
  output differs from the expected value); correct.
- Mutation detection over the task's kept mutants: `filtered` — only correct assertions are kept; `corrected` — all
  valid inputs with expected values replaced by reference outputs; oracle loss = corrected − filtered.
- `buggy` context: whether the suite, with assertions as written, fails on the shown mutant (bug detected), and
  whether its expected values agree with the mutant rather than with the reference (bug encoded).
- Reference point: the original HumanEval tests parsed the same way.

## Statistics

Per-task means; paired bootstrap over tasks (2000 resamples) for differences between contexts within a model. For
the shown mutant, detection by the `buggy` suite is compared with detection of the same mutant by the `spec` suite
of the same task and model (exact McNemar test).
