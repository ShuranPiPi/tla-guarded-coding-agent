# Formal-Spec-Guarded Coding Agent

CE 356 final project: a small coding agent whose workflow is guarded by TLA+
specification generation and mechanical checking with TLC or TLAPS.

## What This Project Verifies

The default success criterion is:

> The agent must produce a TLA+ spec bundle that passes TLC.

In `specification` mode, the first gate is stricter:

> The agent must produce a TLA+ proof module whose theorem passes TLAPS.

Python code generation happens only after the selected checker has passed. If
the Python implementation fails the spec-derived tests, the run ends in
`CodeFail` rather than invalidating the checked spec.

Workflow:

```text
Init -> GenerateSpec -> CheckSpec -> RepairSpec* -> DeriveTests
     -> GenerateCode -> TestCode -> RepairCode* -> Done | CodeFail
                                           CheckSpec* -> SpecFail
```

Terminal states:

- `Done`: the spec passed the selected checker and Python passed spec-derived tests.
- `CodeFail`: the spec passed the selected checker, but Python did not pass generated tests.
- `SpecFail`: no checker-valid TLA+ spec/proof was produced within the retry budget.

## LLM Providers

The provider is selected by `AGENT_PROVIDER`:

- `auto`: prefer OpenAI when `OPENAI_API_KEY` exists; otherwise use Gemini.
- `openai`: use `AGENT_MODEL`, default `gpt-4o-mini`.
- `gemini`: use `GEMINI_MODEL`, default `gemini-3.5-flash`.

Gemini uses the `google-genai` SDK and `gemini-3.5-flash`, matching the Google
Gemini API quickstart and model docs:

- https://ai.google.dev/gemini-api/docs/quickstart
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/rate-limits

Do not commit real API keys. Copy `.env.example` to `.env` and fill local
secrets there.

## Spec Modes

The first specification step is selected by `AGENT_SPEC_MODE` or by the
`spec_mode` argument to `run_agent`:

- `example` (default): ask the model for a compact finite example-based TLA+
  module with `pc`, `Examples`, `TypeOK`, and `Correct`; check it with TLC.
- `specification`: ask the model to first write a structured task
  specification in the JSON block, then encode it as a lower-level finite TLA+
  state machine with `idx`, `checked`, `CheckOne`, `Correct`, and `Safety`;
  require TLAPS to prove `THEOREM ExamplesCorrect == Correct`.

Both modes must pass their checker before Python generation starts. If TLAPM is
not available, `specification` mode fails as `SpecFail`; it does not fall back to
TLC. The runner uses `TLAPM_CMD` when set, then native `tlapm`, then WSL `tlapm`.

## Project Layout

```text
agent/
  graph.py        LangGraph workflow
  nodes.py        workflow node implementations
  llm.py          OpenAI/Gemini provider abstraction
  specs.py        spec bundle parser
  tlc.py          TLC runner
  tlaps.py        TLAPS runner
  tools.py        Python subprocess test runner
  rag.py          repair-pattern retrieval with keyword fallback
tla/
  CodingAgent.tla TLA+ model of the new spec-first controller
  CodingAgent.cfg TLC config
tools/
  tla2tools.jar   TLC runtime used by the project
notebooks/
  01_formal_spec_guarded_agent_demo.ipynb
  02_provider_fallback_demo.ipynb
  03_spec_mode_comparison.ipynb
  archive/        historical draft notebooks, not maintained
```

## Quick Start

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY or GEMINI_API_KEY.

python examples/run_demo.py two_sum
python examples/run_demo.py two_sum --spec-mode specification
python tests/eval.py
python tests/eval.py --compare-spec-modes
python tests/compare_spec_modes.py --runs 5
```

Run TLC on the workflow model:

```powershell
java -cp tools\tla2tools.jar tlc2.TLC -config tla\CodingAgent.cfg tla\CodingAgent.tla
```

## Spec Bundle Format

The LLM is prompted to emit a finite bundle. The parser accepts `tla` and `json`
blocks and synthesizes the TLC cfg from definitions that are actually present in
the TLA module. This reduces Gemini failure modes where the cfg references a
missing invariant or property.

````text
```tla
---- MODULE TaskSpec ----
...
====
```
```cfg
SPECIFICATION Spec
INVARIANTS TypeOK
CHECK_DEADLOCK FALSE
```
```json
{
  "specification": {"behavior": "optional structured task spec"},
  "spec_tests": ["assert function_name(...) == ..."]
}
```
````

In `example` mode, TLA/cfg blocks are checked by TLC. In `specification` mode,
the TLA proof module is checked by TLAPS. The JSON tests are used afterward to
evaluate the generated Python implementation. In `specification` mode, the
optional `specification` JSON object is also passed to the Python generation
prompt.

## Gemini Reliability Strategy

`gemini-3.5-flash` is treated as a small model, so the spec prompt constrains
the task heavily:

- Gemini is asked to follow a complete finite-state TLA+ example template.
- The default template uses one variable, finite literal examples, `TypeOK`, and
  `Correct`.
- The optional `specification` template uses a low-level `idx`/`checked` state
  machine, records a structured task specification in JSON, and requires a TLAPS
  theorem over the finite examples.
- The agent synthesizes the cfg instead of trusting the model's cfg.
- Formal-checker error output is summarized and mapped to concrete repair advice.
- If the model still cannot produce a checker-valid module, the deterministic
  fallback creates a simple finite bundle/proof from public tests.

## Testing

```powershell
$files = @((Get-ChildItem agent -Filter *.py).FullName,
           (Get-ChildItem examples -Filter *.py).FullName,
           (Get-ChildItem tests -Filter *.py).FullName)
python -m py_compile @files
python -m json.tool tasks\sample_tasks.json
java -cp tools\tla2tools.jar tlc2.TLC -config tla\CodingAgent.cfg tla\CodingAgent.tla
```
