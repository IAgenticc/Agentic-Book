# Agentic Systems Engineering: Reference Implementations

Real, tested implementations of both canonical systems from *Agentic Systems
Engineering*: the SRE Agent and the Document Intelligence Agent, sharing one
model interface (`agent_core/`). Every module maps to the chapter that
introduces its pattern. Tests run against `FakeModel`, a deterministic
stand-in, so the whole suite runs offline with no API key required.

## Layout

```
agent_core/            Shared model interface (Chapter 26's Model Fallback)
sre_agent/              Case study: Chapter 41
document_intelligence/  Case study: Chapter 42
tests/                  test_*.py (sre_agent) and test_di_*.py (document_intelligence)
scripts/                Live smoke tests, kept out of the pytest suite
```

## Chapter map

### SRE Agent (`sre_agent/`)

| Module | Chapter | Pattern |
|---|---|---|
| `loop.py` | 4, 5 | Bounded Agent Loop, Deterministic Shell |
| `tools.py` | 16, 20 | Capability-Scoped Tools, Blast-Radius Boundary, Idempotent Tool Action |
| `approval.py` | 18 | Proposal-Approval-Execution |
| `durable_task.py` | 22 | Durable Task Graph |
| `cost_governor.py` | 25 | Cost Governor |
| `circuit_breaker.py` | 27 | Agent Circuit Breaker |
| `ledger.py` | 29 | Audit Ledger |
| `lease.py` | 34 | Resource Lease |
| `orchestrator.py` | 41 (case study) | Everything above, wired into one incident-response flow |
| `api.py` | Appendix C | The same flow behind a real, runnable FastAPI HTTP interface |

### Document Intelligence Agent (`document_intelligence/`)

| Module | Chapter | Pattern |
|---|---|---|
| `schema.py` | 36 | Typed State |
| `blackboard.py` | 35 | The Blackboard Pattern |
| `specialists.py` | 35, 36 | Party/obligation/clause specialists, coordinating through the board |
| `verification.py` | 23 | Verification Gate |
| `risk.py` | 17 | Risk-Tiered Release Gate |
| `evidence.py` | 30 | Evidence-Before-Fact |
| `golden_set.py` | 28 | Golden Set Regression |
| `graph_store.py` | 38 | Neo4j-backed fact graph: same interface as the chapter's NetworkX example, a real graph database underneath |
| `retrieval.py` | 8 | pgvector-backed retrieval: real nearest-neighbor search, not a mock of it |
| `orchestrator.py` | 42 (case study) | Everything above, wired into one document-processing flow |

### Shared (`agent_core/`)

| Module | Chapter | Pattern |
|---|---|---|
| `models.py` | 26 | Model Fallback: `FakeModel`, `AnthropicModel`, `GeminiModel`, `OpenAICompatibleModel` |

## Running the API (Appendix C)

```
cd reference
pip install -e ".[dev]"
uvicorn sre_agent.api:app --reload
```

`POST /incidents` and `GET /incidents/{task_id}/ledger`, backed by exactly `handle_incident`
from `orchestrator.py`. `tests/test_api.py` covers it end to end: concurrent requests racing
for the same lease, a repeated request that doesn't re-run a completed step, a circuit that
opens after repeated failures, and more. Appendix C walks through the same scenarios with
`curl` and explains a real cross-thread SQLite bug this exact code found the first time it
ran behind a real server instead of a direct function call.

## Running the tests

```
cd reference
pip install -e ".[dev]"
pytest -v
```

No API key needed: every test uses `FakeModel`. To use a real model, install
the matching optional extra:

- `pip install -e ".[anthropic]"` → `AnthropicModel()`, set `ANTHROPIC_API_KEY`
- `pip install -e ".[gemini]"` → `GeminiModel()`, set `GEMINI_API_KEY`
- `pip install -e ".[openai-compatible]"` → `OpenAICompatibleModel(model=..., base_url=...)`,
  works against OpenAI itself or any OpenAI-compatible endpoint (Gemini's included)

Never inline an API key in code or commit one to this repo: read it from
an environment variable at runtime.

## Real databases (optional, not part of CI)

`test_di_graph_store.py` and `test_di_retrieval.py` run against a real Neo4j
and a real Postgres+pgvector, not mocks. Both skip automatically if the
service isn't reachable, so the main suite still runs offline without
Docker. To run them:

```
docker run -d --name asr-neo4j -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/testpassword123 neo4j:5-community

docker run -d --name asr-postgres -p 5432:5432 \
    -e POSTGRES_PASSWORD=testpassword123 -e POSTGRES_DB=agentic_ref \
    ankane/pgvector:latest

pip install -e ".[dev]" neo4j "psycopg[binary]" pgvector
pytest tests/test_di_graph_store.py tests/test_di_retrieval.py -v
```

Both found a real, specific bug the first time they ran: pgvector's `<->`
distance operator needs its parameter explicitly cast (`%s::vector`) when
it isn't going into a typed column directly: psycopg won't infer it, and
the error only shows up against a real database, never in a mock.

## Live smoke tests (optional, not part of CI)

Six scripts prove real SDK wiring end to end, deliberately kept out of the
pytest suite: tests should stay fast, free, and deterministic, which a
live network call to a model API is none of.

```
export GEMINI_API_KEY=...   # read from your own env, never hardcoded

python scripts/smoke_test_model_fallback.py
# Chapter 26's fallback chain: a fake failing primary, GeminiModel (the
# real google-genai SDK) as the real "different provider" fallback.

python scripts/smoke_test_openai_compatible.py
# The real `openai` SDK, unmodified, pointed at Gemini's OpenAI-compatible
# endpoint instead of OpenAI's own -- proves one wrapper class covers
# any OpenAI-compatible provider.

python scripts/smoke_test_end_to_end.py
# The FULL SRE Agent handle_incident orchestrator -- ledger, lease,
# circuit breaker, capability scoping, cost governor, approval, durable
# task, idempotency -- with a real live model actually making the
# diagnosis call, and a real (different-SDK) fallback behind it.
# Nothing in this run is FakeModel.

python scripts/smoke_test_end_to_end_fallback.py
# The same full orchestrator, but the primary model name is genuinely
# invalid, so Gemini's own API returns a real error. Proves the
# fallback path itself activates under a real failure, not just that
# it's present and unexercised.

python scripts/smoke_test_document_intelligence.py
# The FULL Document Intelligence Agent process_document orchestrator --
# three specialists coordinating through a real Blackboard, a real
# model actually extracting parties/obligations/clauses, independent
# verification against the source text, risk classification, and an
# evidence-first question answered afterward. Found and fixed two real
# whitespace-normalization bugs in verification.py and evidence.py this
# way -- a wrapped line in the source document broke an exact substring
# check that mocked tests never would have caught.

python scripts/smoke_test_real_document.py
# The same orchestrator run against a genuine public document instead of
# a hand-written sample: a real services agreement pulled from SEC
# EDGAR's full-text filing archive, with real messy formatting. Found a
# second, different whitespace bug this way: ASCII-art dash underlines
# beneath section headings (common in real legal filings) land as a
# stray token mid-sentence once the document is flattened to plain
# text. Fixed in the same normalization step as the first bug.
```

`OpenAICompatibleModel` exists because several providers, Gemini included,
expose an OpenAI-compatible chat-completions endpoint. One wrapper class
covers all of them: only `base_url` and `model` change: confirmed
working end to end against a live Gemini key rather than assumed.

## Design notes

- `lease.py` and `durable_task.py` use SQLite for a real, working demonstration
  of the atomic-write and persisted-status contracts Chapters 34 and 22
  describe. A production deployment would back these with Redis or a proper
  database, but the interface: `acquire`/`release`, `set_status`/`get_status`
 : stays the same.
- `sre_agent/orchestrator.py`'s `handle_incident` and
  `document_intelligence/orchestrator.py`'s `process_document` are the two
  places all of each system's patterns compose. Reading either top to bottom,
  alongside its own comments, is the fastest way to see how the pieces fit
  together.
- `verification.py`'s `verify_extraction` normalizes whitespace, and strips
  runs of dashes/underscores/equals signs, before comparing a claimed quote
  to the source document. Neither was a design decision made up front:
  both were found live: a wrapped line in a hand-written contract, then a
  dash-underlined section heading in a real SEC filing, each breaking an
  exact substring check on a quote the model had gotten completely right.
- `graph_store.py`'s `Neo4jFactGraph` and `document_intelligence/orchestrator.py`'s
  in-chapter NetworkX example share one interface on purpose: `find_affected`
  answers the same question either way, in-process graph or real database,
  exactly the "swap the backend, keep the interface" claim Chapter 38 makes.
