# Goodform — local creator workspace

A working first prototype of a Windows / Apple Silicon creator marketing pipeline. React + TypeScript UI, a Python standard-library API, SQLite persistence, optional local Ollama inference, and a human verification queue. Tauri desktop scaffolding is included; native builds are not yet verified.

## Run the working prototype

Requires Node.js 22.12+ (or a supported newer version), npm, and Python 3.10+.

```sh
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. The launcher starts both Vite and the local API on port 4319. On Windows it uses `python`; on macOS it uses `python3`. Both processes stop with Ctrl+C. No API keys or social credentials are needed to explore the sample workspace.

The sample workspace is clearly labeled and is isolated from imported analytics. The app stores development data in `.data/goodform.sqlite3` (gitignored). Override the database path with `GOODFORM_DB` if needed. Fonts are bundled locally; there are no remote image or font requests.

## Trend research and learning

The new **Trend desk** retrieves current Reddit discussions through approved OAuth access. **Learning journal** links approved video, Reel, tweet and livestream ideas to their published results, compares immutable snapshots against a frozen baseline, and supplies wins and losses to future recommendations. This is retrieval and adaptive creator memory, not model-weight training.

See [Reddit setup and the feedback-loop guide](docs/reddit-and-learning.md).

## Implemented

- Overview, publication-date performance chart, content library, search, platform filters and sorting.
- Validated, atomic CSV/JSON imports into a separate personal workspace. Latest snapshot upserts by platform + post ID, with immutable observation history.
- Deterministic comparative scores with visible formulas, cohort sizes, missing-data handling and observation windows.
- Creator profile: name, niche, voice, goal and local model.
- Distinct video, Reel, tweet and livestream ideas, plus snapshot briefs, ad briefs and collaboration briefs.
- Explicit rule-based template mode when no local model is available. Never disguises a template as AI output.
- Local Ollama `/api/chat` integration with JSON schema validation and bounded generation.
- Editable drafts with frozen source snapshots, verification checklist, approve/request-changes decisions and append-only application-level audit events.
- Approval is bound to the exact title/body hash and revision. Edits clear approval. Stale or repeated decisions are rejected. Only approved content can be exported to Markdown.
- Planned connection cards for 15 platforms. They do **not** claim live integration.

## Human approval contract

The pipeline is **analytics → interpretation → draft → human verification → approval → export**.

Approval requires all three checks: evidence/factual accuracy; creator voice and audience fit; permissions/disclosures/sensitive details. Requesting changes requires feedback. The backend enforces the state transitions, not just disabled UI controls. A changed approved draft must pass review again. Export is not publishing.

This is a single-user local prototype. The app does not establish a cryptographically verified human identity: another process with local API access can issue review requests. Audit records are not tamper-proof against someone who can edit the SQLite file. Before production, add OS/session-bound authentication, reviewer identity, transactional action permits and tamper-evident event storage appropriate to the threat model. The model has no review or publishing tools.

## Local AI

Install Ollama separately and download a model suitable for your RAM/GPU. Set its exact name in **Creator profile**, then use **Check connection**. The default candidate is `qwen3:8b`; it is not downloaded automatically. Choose “Use my local AI model” when creating a draft. Calls go to `127.0.0.1:11434`. There is no cloud fallback. Local hardware benchmarking and model installation UX remain future work.

The prototype supplies a short, curated ruleset and creator context. It does **not** yet implement a full research-backed marketing knowledge library, vector retrieval, specialized training, multimodal video analysis or validated predictive models. A failed model call shows an error; template mode is always an explicit choice.

## Import format

Use the in-app example download or [the schema guide](docs/import-format.md). Platform-native exports must be normalized into this format first. This is not yet a universal platform-export parser.

The database preserves timestamped observations and exposes the latest snapshot per platform/post. The dashboard and brief report cumulative snapshots, not daily gains. The experiment journal evaluates a specified observation window. Automated daily scheduling and daily-delta reporting are not implemented.

## Verification

```sh
npm test
npm run build
```

Tests use temporary SQLite databases. The HTTP test binds an ephemeral loopback port. They cover atomic import validation, workspace separation, comparable scoring, missing values, review checks, stale revisions, rejection feedback, approval invalidation, export gating, content-hash mismatch, persistence, HTTP origins and model failure handling.

## Desktop development

Install the Rust toolchain and Tauri prerequisites for the target operating system. Stop `npm run dev` before launching:

```sh
npm run desktop
```

`npm run desktop:build` is the native packaging entry point. Release scaffolding launches the embedded Python worker using an existing system Python and stores its database in Tauri's application-data directory. **This is not yet a standalone distributable.** A signed release needs a bundled, per-platform worker; runtime readiness and port-conflict handling; an app icon; Windows/macOS CI validation; signing/notarization; and native export-dialog integration. The current browser export uses a Blob download, which has only been checked in the browser development flow.

Rust is absent from the current build environment, so the native shell has not been compiled or tested. Windows execution and Apple Silicon packaging must both be verified before release.

## Not connected yet

Creator-account OAuth applications, connection backend, webhook delivery, token vault, publishing endpoint, paid ad execution, collaborator discovery and outreach remain unimplemented. Reddit has a read-only trend-research connector using locally configured approved credentials; this does not connect your Reddit creator account. Connection cards expose this limitation. See [the architecture and build roadmap](docs/architecture.md) for the next implementation stages.

## Universal public briefing

The Trend desk automatically reads a shared, public briefing. End users need no social login, API keys or local model for this feature. A separate operator worker gathers public sources and generates one versioned edition for all readers, with durable caching and stale fallback. The development launcher starts the public service as well as the local app. [Deploy the shared service](docs/trend-service-deployment.md) and configure its release URL before distribution. Hosting and operator credentials/model setup are still required; no production endpoint is deployed.
