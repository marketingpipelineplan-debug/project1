# Verification — 13 October 2026

## Passed

- `npm run build`: TypeScript strict checking and Vite production bundle.
- `npm test`: 39 automated tests using disposable SQLite databases. Includes immutable observations, matched-window baselines, prospective versus retrospective experiments, successful and unsuccessful outcomes, secondary metrics, workspace isolation, approval revision checks, and mocked Reddit/Ollama adapters.
- Browser intelligence smoke test: Reddit setup status and actionable missing-credentials error; all four idea choices; sample livestream template creation with timed segments and captured provenance; new draft remains pending with approval disabled; learning journal requires an approved idea. The sample livestream draft remains in the sample review queue.
- Trend desk narrow-layout check: no horizontal document overflow. Temporary viewport override reset after testing.
- Browser smoke test: overview loads persisted sample data; library search and platform filtering find the intended post; score details show formula and source values.
- Browser review test on **sample data only**: new brief starts pending; approval is disabled until all checks are selected; approval creates a recorded version; an unsaved edit disables export; saving the edit resets the draft to pending and the checklist to unchecked; history shows the transition. The test draft is left pending, with the test-only approval note retained in history.
- Desktop layout at 1440px and narrow layout at 390px: no horizontal document overflow; navigation drawer opens and navigation works.
- Fonts are bundled, not fetched from a public CDN at runtime.

## Not verified / not implemented

- Real Ollama inference: the runtime is reachable, but no local models are installed. Model success/failure and cloud-model restrictions are covered with mocked adapter responses, not a downloaded model benchmark.
- Native Tauri build: `tauri info` reports Rust/Cargo missing. Native packaging and Windows operation are not verified.
- Live Reddit access is implemented but not verified against real credentials. Authentication, normalization, caching, rate-limit errors and source provenance were tested with mocked responses. The user will configure approved credentials locally; none were entered or inspected during verification.
- Creator social-account connectors and the small hosted connection service are not implemented. No real creator account has been connected or read.
- Automated daily scheduling, historical daily deltas and production media generation are not implemented. Adaptive creator memory updates generation context; it does not train model weights.

The development preview runs on loopback only. In the sandbox, loopback approvals temporarily delayed API connections during startup; the API and browser retry path were verified after the connection became available.

## 14 October update

- Universal briefing endpoint and summary-led Trend desk added; creator data is excluded from the briefing context.
- Production build and all 42 tests pass. New tests cover public-only synthesis context, missing-source behavior and remote-model rejection.
- Live model status: Ollama reachable, zero installed models. Synthesis tests use mocked model responses; real AI inference remains unverified.

### Multi-source follow-up

- 52 tests pass; TypeScript/Vite build passes. Four additional public adapters (YouTube, X, Twitch, Kick) were checked against official API documentation and exercised with mocked responses. No live provider access or model inference is claimed.
- Checks include source normalization, missing metric handling, per-provider partial failure, known-source citations, local model restriction, credential redaction, cache reuse/expiry, provider cooldowns and concurrent generation limits.
- No shared backend was deployed.

### Account-free shared delivery

- All 64 tests pass, including real loopback publisher-to-subscriber delivery and desktop delivery-route checks. Production TypeScript/Vite build passes.
- The separate public worker starts with `npm run dev`; verified it imports no private workspace application.
- Browser smoke check: opening Trend desk automatically loads its delivery state; no account selector, analytics import, provider setup or model-install prompt appears. No briefing exists yet, so the honest waiting state is shown. Screenshot: `docs/screenshots/account-free-trend-desk.jpg`.
- Publisher and subscriber restart/outage persistence, identical edition versions, source contract validation, schedule execution without readers, read-only HTTP routes and private-route isolation are tested with synthetic fixtures in temporary directories. No fixtures were published into the real workspace.
- Docker/systemd deployment artifacts are prepared, not executed (Docker is unavailable on this host). No production domain/hosting selected; release URL remains empty. Live provider credentials, real synthesis and native packaging remain unverified.
# Vercel hosted-service preparation — October 14, 2026

Latest production verification: `marketingpipeline.vercel.app` now serves the
public Trend desk (HTTP 200), confirmed in the browser. Deployment
`dpl_2m2ybZadKpqdZdNhtBjRzrd8tnyj` is READY. The serverless API executes;
`/api/refresh` rejects unauthenticated requests with 401. `/healthz` and
`/api/trends/latest` return a sanitized 503 until Redis is configured. No creator
bootstrap endpoint is hosted. Production build and all 72 backend tests pass.
The earlier permission blocker below was resolved by using the verified project
in the connection's default scope after the user created it through Vercel Drop.
No live generated briefing has been verified; source credentials remain pending.

- Added a stateless public Python handler, AI Gateway synthesis, durable Upstash
  snapshots, authenticated cron refresh, shared cooldown and fenced refresh lock.
- Full backend suite: 72 tests passed. Packaged handler imported successfully.
- Deployment package uses an explicit public-source allowlist.
- Live deployment not completed: Vercel returned 403 when creating the project
  in SherHiKehde; team-scoped project listing is empty. No local CLI login exists.
- No real hosted-model, Redis or social-provider request was verified. See
  [Vercel deployment setup](vercel-trend-deployment.md) for pending configuration.

# Brain studio integration — October 28, 2026

- UI → prepare API → persisted context → UI verified in the browser using sample
  data. No console errors. Screenshot: `screenshots/brain-studio.png`.
- Hosted generation is disabled because the backend has no configured API key.
  No paid model request, fine-tuning job or deployment was performed.
- Mocked model output → saved session → pending draft → exact-version approval →
  export tested in isolated databases, including post-edit approval invalidation.
- Duplicate requests, failed calls, expired context, workspace separation and stale
  trend exclusion tested. Full suite: 92 passing tests; frontend build passes.
- Models remain the provisional candidates from the October 14 workbench. Their
  live output quality and native desktop packaging remain unverified.

