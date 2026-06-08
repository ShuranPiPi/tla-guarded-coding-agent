# TLA+ controller model

`CodingAgent.tla` models the spec-first workflow implemented by
`agent/graph.py`:

```text
Init -> GenerateSpec -> CheckSpec -> RepairSpec* -> DeriveTests
     -> GenerateCode -> TestCode -> RepairCode* -> Done | CodeFail
                                           CheckSpec* -> SpecFail
```

The model abstracts LLM behavior as nondeterministic booleans:

| Python state field | TLA+ variable |
|---|---|
| `workflow` | `pc` |
| `spec_result["passed"]` | `specOk` |
| TLC check completed | `specChecked` |
| `spec_tests` derived from verified bundle | `testsDerived` |
| `last_result["passed"]` | `codeOk` |
| Python test completed | `codeChecked` |
| `spec_retries` / `code_retries` | retry counters |

## Checked properties

- `SpecCheckedBeforeCode`: Python generation/testing cannot start until the
  TLA+ spec has passed TLC and spec-derived tests exist.
- `NoDoneWithoutVerifiedSpec`: `Done` requires both a verified spec and passing
  Python tests.
- `SpecFailOnlyAfterBudget`: spec failure is reachable only after the spec
  retry budget is exhausted.
- `CodeFailPreservesSpecSuccess`: Python failure does not erase the fact that
  the spec passed TLC.
- `BoundedRetries`: both retry counters stay within their budgets.
- `EventuallyTerminates`: under weak fairness, the workflow eventually reaches
  `Done`, `CodeFail`, or `SpecFail`.

## Running TLC

```powershell
java -cp tools\tla2tools.jar tlc2.TLC -config tla\CodingAgent.cfg tla\CodingAgent.tla
```
