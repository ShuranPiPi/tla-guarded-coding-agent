# TLA+ specification

`CodingAgent.tla` formalises the state machine implemented by
`agent/graph.py`. The Python implementation and the TLA+ model share the
same vocabulary:

| Python (`agent.state`)      | TLA+ variable   |
|-----------------------------|-----------------|
| `workflow` (`Init`/`Generate`/`Test`/`Repair`/`Done`/`Fail`) | `pc` |
| `last_result["passed"]`     | `codeOk`        |
| *did we just run `test_node` on this code?*                  | `tested`        |
| `retries`                   | `retries`       |
| `max_retries`               | `MaxRetries` (constant) |

## Properties

All four come directly from the proposal:

1. **NoAcceptBeforeValidation** (invariant) — `pc = "Done" ⇒ tested`.
   The agent cannot land in `Done` without having run at least one
   `TestPass` transition.
2. **FailedTestGoesToRepairOrFail** (invariant) — after a failed test the
   controller never skips back to an accept state.
3. **BoundedRetries** (invariant) — `retries ≤ MaxRetries`. The retry
   budget can never be exceeded.
4. **EventuallyTerminates** (liveness) — `◇(pc ∈ {Done, Fail})`. Under
   weak fairness the workflow always makes progress and eventually halts.

## Running TLC

```bash
# Get tla2tools.jar from https://github.com/tlaplus/tlaplus/releases
java -cp tla2tools.jar tlc2.TLC -config CodingAgent.cfg CodingAgent.tla
```

With `MaxRetries = 3` the state space has 36 distinct states and TLC
finishes in well under a second. Increase `MaxRetries` in `CodingAgent.cfg`
to stress-test the bound.
