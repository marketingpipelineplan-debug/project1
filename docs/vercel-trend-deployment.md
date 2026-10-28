# Shared Trend desk on Vercel

Status: deployed at https://marketingpipeline.vercel.app on October 14, 2026.
Project: `marketing_pipeline` (`prj_biuhojfK3ZewBMYy3pdPLfQVrthr`).
Deployment: `dpl_2m2ybZadKpqdZdNhtBjRzrd8tnyj`, READY.
The connected tool's default scope accesses this project; explicitly passing the
team ID unexpectedly returned empty/not-found responses. Use the verified project ID.

Homepage: HTTP 200. Python briefing and health routes execute, returning sanitized
503 responses because Redis is not configured. Unauthenticated refresh: HTTP 401.
CRON_SECRET is configured, project OIDC is enabled, and production is public while
preview protection remains enabled. No live model or social-source call is verified.
The production frontend displays the public Trend desk; local/native builds retain
the private workspace. The desktop release URL remains unset until a real briefing
can be verified. Redis and approved source credentials remain required.

The hosted service uses Python Functions, Vercel AI Gateway and Upstash Redis.
Redis provides durable last-good briefings, an atomic refresh lease and a shared
15-minute retry cooldown. Desktop users only read `/v1/briefing`; they never
provide social credentials or trigger inference. No creator analytics leave the
device through this service. Existing local creator generation remains unchanged.

## Deploy

1. Reuse `marketing_pipeline` for the combined public UI and API. The root
   `vercel.json` builds with `VITE_PUBLIC_HOSTED=true` and wires the Python API.
2. Connect a durable Upstash Redis database using Vercel Marketplace; configure
   `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` in Production.
   Use a dedicated database; do not enable eviction of the saved briefing.
3. Enable project OIDC for AI Gateway. Alternatively configure an
   `AI_GATEWAY_API_KEY` in Vercel. Gateway access/credits must be available.
   `AI_GATEWAY_MODEL` defaults to `google/gemini-2.5-flash-lite`, verified in the
   live model catalog on October 14, 2026. This is a low-cost summarization model,
   not a custom-trained marketing model. It has not yet been live-tested here.
4. Set a cryptographically random `CRON_SECRET` in Vercel. Never put it in source,
   a URL, screenshots or chat. The refresh route rejects requests if it is absent.
5. Configure approved operator source credentials. For Reddit prefer
   `GOODFORM_REDDIT_CLIENT_ID`, `GOODFORM_REDDIT_REFRESH_TOKEN`,
   `GOODFORM_REDDIT_USER_AGENT`, and client secret if required by the Reddit app.
   An expiring `GOODFORM_REDDIT_ACCESS_TOKEN` is also supported. YouTube uses
   `GOODFORM_YOUTUBE_API_KEY`; optional `GOODFORM_TREND_REGION` defaults to `US`.
   See `public-trends.md` for other providers and current coverage limitations.
6. For the combined site, deploy the frontend source, package files, Vercel config,
   `api/index.py`, `requirements.txt`, `.python-version`, and the four public
   Python modules only. Respect `.vercelignore`; never upload `.data` or secrets.
   For a separate API-only project, `python3 scripts/package-vercel-trends.py`
   creates an isolated package in `dist/vercel-trends`.
7. Verify the deployed `/healthz` and `/v1/briefing` without authentication. Keep
   production public so installed desktops can read it. `/api/refresh` remains
   protected by its own bearer secret. Run one authorized refresh and check its
   result, then verify that the public report has valid citations and coverage.
8. Only after verification, run
   `python3 scripts/configure-trend-release.py --url https://YOUR-PRODUCTION-ORIGIN`
   and rebuild the desktop release. The release URL is deliberately still blank.

The initial cron schedule is once daily at 03:00 UTC (08:30 India time), compatible
with Hobby scheduling limits. Exact execution time depends on the Vercel plan.
More frequent refresh needs a compatible plan and an intentional schedule change.
The existing desktop freshness rule still flags reports older than 30 minutes;
daily refresh therefore does not promise continuously current trends.

Public requests only read storage. Failed provider requests, missing evidence,
invalid citations, gateway failures and expired leases never replace the last
good briefing. Invalid configuration returns a sanitized 503. Cron failures can
be investigated in Vercel; no raw provider errors or credentials are returned.

## Verification

`tests/test_vercel_trends.py` covers cron authorization, public read isolation,
durable delivery, duplicate-refresh suppression, retry cooldown, invalid output,
expired lease fencing, model input isolation and sanitized errors. Live Vercel,
Redis and Gateway verification remains pending project access and configuration.
