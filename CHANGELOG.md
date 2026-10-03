# Deviations from PROTOCOL.md

1. Literal storage fixed after the DeepSeek-V3.2 generations and before the local ones (2026-10-03). Task inputs and
   outputs were stored as JSON, which turns tuples into lists, so for functions returning tuples (for example
   HumanEval/148) the stored reference outputs differed in type from the real ones. Literals are now stored as Python
   source (`repr`) and assertions are parsed from the raw model text at scoring time. Rebuilding the mutants changed
   the kept set of one task (HumanEval/148: 1,227 mutants in total became 1,226); the mutant shown in the `buggy`
   context stayed the same for every task, so no generation was repeated.
2. One descriptive measure added to the `buggy` analysis after the results were seen (2026-10-03): among the
   assertions that fail on the shown mutant, the share whose expected value is the reference output, i.e. how often
   a failure reported to the developer points at the real bug rather than at a wrong expected value.
3. Scoring corrected after the scoring code was re-checked (2026-10-03); all suites were rescored from the stored replies.
   (a) A child process that crashed or timed out on one input used to mark every remaining input of the suite as a
   timeout; outcomes are now streamed per input and a new child continues after a crash or timeout (mutant
   screening keeps its original rule, so `data/mutants.json` is unchanged). (b) Assertions of the forms
   `f(args) is v`, `f(args)` and `not f(args)` were compared with `==`; they are now evaluated as written.
   (c) The original HumanEval tests were cut to six assertions like the generated suites; they are now used in full,
   and the comparison with them is made on the functions whose original tests could be parsed.
   (d) The protocol defines detection of the shown bug by "assertions as written"; the paper reports both this raw
   failure and detection by a correct assertion, and the composition of the failing assertions is exploratory.
