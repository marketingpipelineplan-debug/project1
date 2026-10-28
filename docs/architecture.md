# Architecture and next stages

## Update — 13 October 2026

`server/intelligence.py` implements the controlled Reddit research tool, timestamped observation storage, experiment plans, evaluation and creator-memory retrieval. `src/Intelligence.tsx` implements Trend desk, Learning journal and research provenance in human review. The native worker scaffold now embeds both Python modules. See [the research and learning guide](reddit-and-learning.md) for current contracts.

Historical observations and Reddit research are now implemented; the original staged roadmap below retains the wider production work still needed, including account-level identity, licensed feeds, scheduling and native release validation.


## Boundaries

- `src/`: React UI, explicitly separate demonstration/imported workspaces; review is the final gate.
- `server/app.py`: local-only Python API, deterministic analytics, SQLite persistence, import validation, model adapter and review state machine.
- `src-tauri/`: Tauri wrapper scaffold for Windows and Apple Silicon. Unverified native builds; system Python is still required.
- `tests/`: temporary-database tests for workflow and invariants, plus local HTTP checks.
- Connection backend: planned, not implemented. Credentials have not been requested or stored.

The default API accepts loopback hosts and an exact origin allowlist, requires JSON for mutations, limits request sizes, and binds only to 127.0.0.1. These checks reduce browser cross-origin abuse; they do not authenticate other local processes. SQLite is not application-encrypted in this prototype. Use the OS account and disk protections during development; production needs explicit credential-vault and database protection decisions.

## Human gate

Every generated draft starts `pending`, revision 1. The model output schema has only `title` and `body`; it cannot set status or invoke approval.

- `pending → approved`: all verification checks true; stores decision, exact content hash and revision.
- `pending → rejected`: requires reviewer feedback.
- `pending/approved/rejected → pending`: explicit edit; invalidates approval, clears review note, increments revision.
- Every mutation verifies the previous revision inside a write transaction.
- Only the approved exact content hash can be exported. No publishing/ad-spend/outreach routes exist.

Later, a publish intent must bind account + destination + content hash + media hashes + schedule + spend ceiling (if applicable). Human approval should authorize that specific intent, not all future actions. Changing any material parameter must invalidate the permit. Do not let a background sync job or a language model mint an approval. Add reviewer authentication before multi-user use.

## Next implementation stages

1. **Native runtime:** bundle the worker for both operating systems; health/readiness handshake; dynamic per-session port and authentication; single-instance protection; native save dialogs; packaged smoke tests and signing.
2. **YouTube first:** register OAuth app, implement authorization state/PKCE where supported, refresh/revocation, least-privilege read scopes, secure token storage, incremental ingestion, quotas and retry/backoff. Preserve actual timestamps and metric definitions.
3. **Small connection backend:** manage only platform-required secrets/token exchange, webhook receipt and bounded delivery queues. No model inference or persistent analytics/content copies by default. Validate webhook signatures and idempotency; implement TTLs and disconnect deletion. Some platforms may need encrypted server-held refresh tokens.
4. **Historical analytics:** account ownership, multiple accounts per platform, immutable timestamped metric observations, metric provenance, definition/version registry, platform-specific comparability and zero/missing distinctions. Daily deltas require compatible observations; do not subtract different reporting windows.
5. **Knowledge and evaluation:** curated licensed/research-based marketing library, citations, local retrieval, representative comment sampling, testable recommendations, creator-rated outcomes, evidence accuracy evaluations, hardware latency benchmarks. Fine-tune only if measured improvements justify it.
6. **Daily workflow:** OS-aware scheduler, missed-run catch-up, creator timezone, platform data-delay labels, no fabricated same-day changes. The current “Daily brief” is an on-demand latest-snapshot brief.
7. **More integrations:** Instagram/Facebook, then TikTok, Pinterest, Twitch, Kick, Tumblr, X, Threads, LinkedIn, Snapchat, Reddit, Bluesky and Mastodon as permissions and supported metrics permit. Publish a per-connector capability matrix; dashboard access is never assumed from login alone.
8. **Trend and collaboration features:** timestamped permitted public data feeds, niche/region relevance, saturation signals, verified partner metadata and transparent uncertainty. No claim of audience overlap without data.
9. **Action execution:** creator-approved exports first; then explicit publish/schedule intents with immutable approvals, revocation, idempotency and an activity ledger. Ads, outreach and media generation remain separate capabilities.

## Current product claims

The UI labels synthetic sample data, template vs AI generation, unknown scores, unconnected integrations and snapshot limitations. Charts plot per-post cumulative snapshot values by publication date. Aggregated views across platforms are not unique people. Average retention is unweighted across available records. No external trend score or specialized marketing model is claimed.
