# Universal public Trend desk

The desk is independent of creator profiles, connected creator accounts, imported posts and learning history. The same public collection settings apply to everyone on one service. The creator's private performance feedback remains in the Learning journal.

## Working implementation

The app now **subscribes to an operator-owned shared service**. It does not collect or synthesize Trend desk content on the user's device. See [deployment guide](trend-service-deployment.md) for the service, release configuration and failure behavior.

`GET /api/trends/latest` on the local workspace API reads the shared public briefing, caches it to disk and returns the last available edition on failure. Legacy trend routes are delivery aliases only. The separate `server/trend_service.py` worker collects sources every 15 minutes and publishes a validated snapshot through a read-only `/v1/briefing` endpoint. Reads never trigger generation. No model, credentials or social account are needed on end-user devices for this desk.

Up to 20 records per source are collected. API results and successful summaries are reused for 15 minutes. Provider failures leave successful evidence available; failed synthesis preserves the previous published edition. HTTP 429 Retry-After seconds are respected by the newer adapters. No scraper fallback exists. This is controlled orchestration, not autonomous planning, reinforcement learning or model-weight training.

## Environment setup

For operators only: configure approved application credentials on the shared backend host, never in frontend code or Git. `.env` files are not automatically loaded. Restart after changing configuration. Values are never returned in status responses. Existing access tokens are used as supplied; Twitch, Kick and X automatic token refresh is not implemented.

| Public source | Environment variables | What is collected |
| --- | --- | --- |
| Reddit | `GOODFORM_REDDIT_ACCESS_TOKEN`, `GOODFORM_REDDIT_USER_AGENT` (or documented refresh credentials) | Hot r/popular discussion sample |
| YouTube | `GOODFORM_YOUTUBE_API_KEY` | Most-popular regional video chart; current chart coverage is limited |
| Twitch | `GOODFORM_TWITCH_CLIENT_ID`, `GOODFORM_TWITCH_ACCESS_TOKEN` | First 20 streams ordered by current viewer count |
| Kick | `GOODFORM_KICK_ACCESS_TOKEN` | v2 active-stream sample, oldest-first; not a popularity leaderboard |
| X | `GOODFORM_X_BEARER_TOKEN` | Provider trends for the selected WOEID |

`GOODFORM_TREND_REGION` defaults to `US` for YouTube. `GOODFORM_TREND_WOEID` defaults to `1` (worldwide) for X. These are deployment settings, not creator personalization. The scope appears in coverage details; mixed geographic scopes are not described as comprehensive global coverage.

`GOODFORM_TREND_MODEL` defaults to `qwen3:8b`. Download and run a local Ollama model before AI synthesis can succeed. Cloud/remote model aliases are rejected. Missing inference leaves source evidence available but does not substitute a template and label it AI.

## Remaining integrations and shared service

Instagram, TikTok, Facebook, Pinterest and Tumblr public discovery are **not implemented**. They must not be represented as scanned. Access scope, permitted commercial use and appropriate provider products must be established per integration. Private creator-account analytics APIs are not substitutes for general public trend discovery.

A standalone public worker/API, durable snapshot, read-only desktop subscriber and release configuration are now implemented. Hosting and a production domain are not yet selected. Use [the deployment guide](trend-service-deployment.md) to deploy the public service and bake its HTTPS address into the release. Do not expose the private workspace API. No external publication has been performed.

## Measurement boundaries

Views, current live viewers, net votes and post counts are not interchangeable. They retain their units. There is no universal numeric trend score. A single snapshot does not prove acceleration, causation or future creator performance. Public titles are treated as untrusted model context. Canonical links are constructed from validated IDs/slugs, external redirects are rejected, responses are bounded and errors avoid credential-bearing URLs.

## Official API references checked 14 October 2026

- [YouTube videos.list](https://developers.google.com/youtube/v3/docs/videos/list)
- [YouTube chart coverage](https://developers.google.com/youtube/v3/guides/implementation/videos)
- [Twitch Get Streams](https://dev.twitch.tv/docs/api/reference/#get-streams)
- [Kick public OpenAPI schema](https://api.kick.com/swagger/doc.json)
- [X Trends by WOEID](https://docs.x.com/x-api/trends/trends-by-woeid/introduction)
- [TikTok research eligibility](https://developers.tiktok.com/products/research-api/)
