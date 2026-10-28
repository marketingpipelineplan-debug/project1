# Phase 2: human feedback and blind evaluation — October 28, 2026

Strategy-v3 adds a quality review under every generated Brain studio direction.
Rate all six dimensions, explain the verdict, and choose keep/revise/reject.
Ratings never approve drafts or count as measured performance. Optional reuse
includes the latest review in future context previews for the same workspace,
creator profile and format (up to six reviews, including rejected ideas).
Unchecking reuse excludes the review from newly prepared briefs. Existing frozen
briefs are unchanged; prepare a new brief to remove previously included feedback.
Append-only revisions retain provenance and prevent stale browser saves from
silently overwriting a newer review. No feedback is used for weight training.
This is local workspace isolation, not cloud user authentication.

The offline comparison tool shuffles model answers and removes model metadata.
It requires matching cases, context and brain versions; the reviewer receives
only `review.json`, while the operator retains `private-mapping.json`. Free text
could still reveal model identity; metadata removal is not a guarantee of blinding.

After generating real reports with the existing evaluator:

```sh
python3 scripts/review-brain.py package .data/sonnet-evaluation.json .data/gemini-evaluation.json --directory .data/blind-review
# Reviewer fills scores, notes and unsupported_claim in review.json.
python3 scripts/review-brain.py score .data/blind-review/review.json .data/blind-review/private-mapping.json --output .data/quality-summary.json
```

Each item evaluates the complete set of three directions, not one selected winner.
Scores remain blank until a human rates them. Reports expose reviewed/expected
counts, per-dimension medians, and flagged unsupported claims. Every item must
be reviewed, every dimension median must reach 4, and no unsupported claim may
be flagged to meet the proposed development target. This does not establish
production quality, statistical superiority or automatically promote a model.
The suite remains eight synthetic development cases, not a held-out benchmark.
The evaluator now records exact context and request latency for live runs.

Verification: 101 backend tests pass and the frontend production build passes.
Eight offline prompts prepared successfully. Tests use mocked inference and
isolated databases; no live quality scores or paid calls were produced. The key
is still absent. New rating controls have build validation but have not yet been
exercised against a real model result in the browser. Native packaging not tested.
Deployment remains paused.

Evaluation design follows [OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices): task-specific cases, human judgment, randomized blind review, and explicit acceptance criteria.

---

# Goodform brain: development workbench

Deployment is paused. On October 28, Brain studio was integrated into the private
development app. Open `http://127.0.0.1:5173`, then **Brain studio**. It remains
separate from the public Vercel API. No paid generation has run during development,
and no model weights have changed.

## Brain studio workflow (strategy-v2)

1. Choose a format and model, and enter the audience, topic and production constraints.
2. Prepare context. The server selects up to eight recent same-format creator posts
   (with up to three comments each), or clearly labels a mixed-format fallback.
   This selects recent observations rather than only high performers. Synthetic
   sample data is labeled and never mixed into imported-workspace context.
3. The existing learning module supplies this workspace's comparable prospective
   experiment patterns, including failures. Optional public trend evidence is
   included only when the shared delivery is current; there is no invented fallback.
4. Inspect the frozen context. Confirm sending it through AI Gateway. The model key
   belongs in the backend process environment (`AI_GATEWAY_API_KEY`), never the
   browser. Restart the backend after configuring it. No key means generation is
   disabled; preparation and inspection still work.
5. Generate three directions. Server-owned prompts and context are persisted before
   inference. A prepared session expires after 15 minutes. Duplicate completed
   requests return the saved result; running/failed sessions cannot silently retry.
6. Choose any direction, not just the model's preference. The candidate becomes an
   ordinary pending draft with frozen evidence and session provenance. Repeating
   this action opens the same draft. Exact-version human approval is still required
   for export; subsequent edits invalidate it.

Sessions persist in `brain_runs` in the workspace SQLite database. This is a local
development integration, not the planned authenticated multi-user cloud backend.
No social publishing, retraining, automatic approval or independent critic agent
has been added. A process interrupted during inference leaves a running session;
prepare a new one after checking for completion rather than automatically retrying
an ambiguous paid call. Historical session context can contain private analytics.

Verification: build passes; 92 backend tests pass. Browser preparation created a
saved session with 24 sample evidence items, showed the missing-model-key state,
and correctly disabled generation. Browser console had no errors. Hosted inference
and idea quality remain unverified. The downstream draft/approval flow was checked
with mocked model output in an isolated test database. Native Rust build was not run.

## Model decision, October 14, 2026

Start with `anthropic/claude-sonnet-5.5` for strategy and creative briefs. Compare
`google/gemini-3.5-flash` using the same inputs. Both IDs were checked against the
live AI Gateway catalog. This is a provisional engineering choice, not a claim
that Sonnet is the best marketing model. Provider benchmarks do not establish
Goodform performance.

Catalog standard token prices at inspection: Sonnet $2/million input and
$10/million output; Gemini 3.5 Flash $1.50/million input and $9/million output.
Illustratively, 6,000 input + 3,000 output tokens would cost about $0.042 and $0.036
respectively, before other provider charges and any pricing changes. Actual use
is recorded when available. There is no automatic retry or fallback model spend.

Sources: https://ai-gateway.vercel.sh/v1/models,
https://www.anthropic.com/claude-sonnet-5-5,
https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions.

## What exists

- `server/brain.py`: bounded context preparation, stale-trend exclusion, prompt
  assembly, explicit hosted inference, structured output validation and review gate.
- `server/brain_playbook.json`: a small versioned seed playbook. Platform guidance
  has source links; editorial heuristics are explicitly labeled as hypotheses or
  product standards. It is not a comprehensive psychology library.
- `evals/brain/cases.json`: eight synthetic development cases, not real creator
  evidence and not a held-out benchmark. They cover all six creative formats.
- `scripts/brain-workbench.py`: inspect a single prompt or explicitly run it.
- `scripts/evaluate-brain.py`: run the scenarios offline or against one model.
  Reports leave human scores blank; passing structure never produces a quality score.

The prompt asks for three distinct concepts and a concise selection rationale.
Each concept needs a hook, payoff, production plan, creator fit, evidence references,
hypothesis, one changed factor, primary metric, observation window and confounders.
It can propose evergreen experiments without trend evidence. Model self-critique
is a prompt instruction, not an independently verified critic or agent loop.

The validator checks required fields, references to supplied non-stale evidence,
duplicate titles/hooks, tweet length and measurement structure. It cannot prove
that a citation supports a claim, that prose is original, or that a production plan
is feasible. A human must inspect these. Likewise placing source text in a data
message reduces confusion but does not guarantee prompt-injection resistance.

## Run locally

Offline, no credentials or model call:

```sh
python3 scripts/brain-workbench.py evals/brain/example-brief.json --output .data/brain-prompt.json
python3 scripts/evaluate-brain.py
```

For real evaluation, configure `AI_GATEWAY_API_KEY` securely in the local process
environment. The workbench does not load `.env` automatically. Never put the key
in a brief, source file, command argument or chat. Inspect the input before adding
`--live`: it sends the supplied creator brief and evidence to the hosted model.

```sh
python3 scripts/evaluate-brain.py --live --output .data/sonnet-evaluation.json
python3 scripts/evaluate-brain.py --live --model google/gemini-3.5-flash --output .data/gemini-evaluation.json
```

Each live suite makes at most eight calls, stopping on the first failure. Outputs
remain in ignored `.data`. They do not enter the app's approval queue or publish.
Private workspace context must eventually be assembled from authenticated user
records; this workbench accepts only explicit input and is not a multi-user API.

## Human evaluation and promotion

Score grounding, creator fit, originality, execution detail, measurement and voice
from 1 (unusable) to 5 (ready with minor edits). A 3 needs substantive editing.
Shuffle outputs and hide model names during review. A reviewer should explain
which sentence or production choice earned each rating.

Suggested initial acceptance target (not an achieved result): median >=4 on every
dimension, no fabricated supporting metrics or citations, no publication without
approval, and all structural checks passing. Report sample counts, individual
failures, latency and cost. Repeat each case to assess variability. Add real,
consented briefs across niches and languages; keep an untouched evaluation set
separate from prompt development before making a production-quality claim.

## How it improves

1. Knowledge: curate licensed/owned marketing and psychology guidance, with source,
   scope, review date and counterexamples. Do not ingest whole books indiscriminately.
2. Fresh evidence: fetch current platform signals; store repeated observations to
   distinguish growth from popularity. Current workbench freshness is a configurable
   future policy; v1 uses a fixed 48-hour cutoff and does not calculate acceleration.
3. Creator memory: use this creator's comparable prospective experiments, including
   failures. Brain studio now connects the existing learning module automatically;
   the standalone CLI still accepts explicit supplied memory.
4. Human feedback: record original output, edits, preference rationale, model and
   prompt versions, source context, approval and subsequent outcomes separately.
5. Weight training, only if justified: select a provider/model that supports the
   intended fine-tuning method. Sonnet selection does not imply fine-tuning access.
   Use rights-cleared, opted-in, reviewed examples with creator/time-separated
   train/validation/test splits. Keep trend snapshots out of enduring factual weights.
   Compare a tuned candidate against this prompting baseline before adoption.

No RL or autonomous self-training is implemented. Views are a noisy delayed signal;
optimizing only views can reward clickbait or paid distribution. Future experiments
need retention, audience satisfaction, feasible production and approval as separate
criteria. Historical correlations cannot establish why a post succeeded.

## Current verification

Ten focused tests pass, including stale/unknown references, duplicate evidence,
review-state enforcement, malformed plans, tweet length, missing credentials and
a mocked Gateway response. Eight offline prompts were generated. Live model
quality, provider compatibility and comparative scores remain unverified.
