# TLC-Spec-Guarded Coding Agent

CE 356 final project: a small coding agent whose workflow is guarded by TLA+
specification generation and TLC model checking.

## What This Project Verifies

The primary success criterion is now:

> The agent must produce a TLA+ spec bundle that passes TLC.

Python code generation happens only after the TLA+ spec has passed TLC. If the
Python implementation fails the spec-derived tests, the run ends in `CodeFail`
rather than invalidating the verified spec.

Workflow:

```text
Init -> GenerateSpec -> CheckSpec -> RepairSpec* -> DeriveTests
     -> GenerateCode -> TestCode -> RepairCode* -> Done | CodeFail
                                           CheckSpec* -> SpecFail
```

Terminal states:

- `Done`: TLA+ spec passed TLC and Python passed spec-derived tests.
- `CodeFail`: TLA+ spec passed TLC, but Python did not pass generated tests.
- `SpecFail`: no TLC-valid TLA+ spec was produced within the retry budget.

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

## Project Layout

```text
agent/
  graph.py        LangGraph workflow
  nodes.py        workflow node implementations
  llm.py          OpenAI/Gemini provider abstraction
  specs.py        spec bundle parser
  tlc.py          TLC runner
  tools.py        Python subprocess test runner
  rag.py          repair-pattern retrieval with keyword fallback
tla/
  CodingAgent.tla TLA+ model of the new spec-first controller
  CodingAgent.cfg TLC config
tools/
  tla2tools.jar   TLC runtime used by the project
notebooks/
  01_tlc_spec_guarded_agent_demo.ipynb
  02_provider_fallback_demo.ipynb
  archive/        historical draft notebooks, not maintained
```

## Quick Start

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY or GEMINI_API_KEY.

python examples/run_demo.py two_sum
python tests/eval.py
```

Run TLC on the workflow model:

```powershell
java -cp tools\tla2tools.jar tlc2.TLC -config tla\CodingAgent.cfg tla\CodingAgent.tla
```

## Spec Bundle Format

The LLM must emit one bundle with three fenced blocks:

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
{"spec_tests": ["assert function_name(...) == ..."]}
```
````

Only TLA/cfg blocks are checked by TLC. The JSON tests are used afterward to
evaluate the generated Python implementation.

## Testing

```powershell
$files = @((Get-ChildItem agent -Filter *.py).FullName,
           (Get-ChildItem examples -Filter *.py).FullName,
           (Get-ChildItem tests -Filter *.py).FullName)
python -m py_compile @files
python -m json.tool tasks\sample_tasks.json
java -cp tools\tla2tools.jar tlc2.TLC -config tla\CodingAgent.cfg tla\CodingAgent.tla
```
