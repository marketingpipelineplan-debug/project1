# Account-free Trend desk: operator deployment

## Architecture

Operator public adapters → scheduled worker → local-to-backend Ollama synthesis → validated, versioned public snapshot → read-only HTTPS endpoint → desktop cache → automatic display.

No social login, platform token or local model is required on the end user's device for the Trend desk. Personalized drafting remains a separate local feature. The desktop does not send creator posts, identifiers, profile information or analytics to the service. Ordinary network connection metadata such as the client's IP address remains visible to the hosting infrastructure.

The shared service does not import `server/app.py`, open the creator database or expose private workspace routes. Do not host the private local API as the trend backend.

## Development

Run `npm run dev`. It starts:

- Public worker/API on `127.0.0.1:4320`.
- Private local workspace API on `127.0.0.1:4319`.
- Frontend on `127.0.0.1:5173`.

The development script points the desktop reader at the public worker automatically. Collection runs at service startup and every 15 minutes, even with no users viewing the desk. Operator credentials and a model must exist on the worker host to produce a real first edition. Without them the UI automatically shows an honest waiting state; there is no synthetic news fallback and no user setup prompt.

## Deploy the public service

No provider or domain has been selected; no deployment has been performed. The files below are ready for an operator to deploy and configure.

1. Copy `server/trend_service.py`, `server/trend_contract.py`, `server/intelligence.py` and `server/public_trends.py` onto a backend host. Python 3.11+ is sufficient; there are no pip dependencies.
2. Configure approved public API credentials using the table in [public-trends.md](public-trends.md). These are operator-owned credentials, supplied only to the backend environment. Existing Twitch/Kick/X tokens must be renewed by the operator; automatic refresh for them is not implemented.
3. Run an Ollama instance with the selected downloaded model. `GOODFORM_TREND_MODEL` defaults to `qwen3:8b`. `GOODFORM_TREND_MODEL_ENDPOINT` defaults to `http://127.0.0.1:11434`; for containers it may point to an operator-controlled internal Ollama service. It receives public evidence only. Remote/cloud model aliases are rejected.
4. Set `GOODFORM_PUBLIC_TREND_STORE` to a persistent writable file, e.g. `/var/lib/goodform-trends/briefing.json`. The worker atomically replaces it only after valid synthesis. Preserve its volume across restarts.
5. Start `python3 server/trend_service.py`. It binds loopback by default. Put a TLS reverse proxy in front of port 4320, exposing only `/v1/briefing` and optionally `/healthz`. Apply ordinary request limits and response caching at the proxy. Never expose the Ollama port or private workspace API.
6. Check `/healthz` and `/v1/briefing`. Health reports whether a first edition exists. All clients receive the same stored edition and `version`; GET never triggers inference or collection. POST is rejected.

### Deployment artifacts

- `deploy/trends.service`: systemd unit for a VM. Provision the `goodform` account, `/opt/goodform` source and `/etc/goodform/trends.env` before enabling it. Store environment secrets outside the repository with restricted file permissions.
- `deploy/trends.Dockerfile`: public service only, non-root UID 10001. Build with `docker build -f deploy/trends.Dockerfile -t goodform-trends .`. Mount a writable volume at `/data`, pass operator environment variables at runtime, and configure the internal model endpoint. Publish the service port to a TLS proxy only. Docker deployment and systemd installation have not been executed in this workspace.

Use one worker replica with its persistent volume initially. Multi-replica leader election and distributed scheduling are not implemented. Scale read traffic through the proxy/cache first.

## Configure the release once

After the backend has a real HTTPS address:

```sh
python3 scripts/configure-trend-release.py --url https://YOUR-PUBLIC-SERVICE-HOST
npm run desktop:build
```

Replace the placeholder with the deployed address. This writes the non-secret public address into `server/release_config.json`, which is embedded in desktop builds. It is an operator release step, not a user setting. The current release file intentionally has no invented production URL. `GOODFORM_TREND_SERVICE_URL` is a development/operator override only.

## Delivery and failure behavior

- The app fetches automatically on opening the desk, every five minutes while visible, and when returning to the tab. The button only checks for an already-published update.
- The desktop reader rate-limits fetches to once per minute and sends a plain GET with no authorization or creator payload.
- Both publisher and desktop retain the last valid edition on disk. A failed synthesis never overwrites a good edition with an empty response.
- Network failures, provider failures, an invalid summary or an invalid response leave the previous edition visible with its original timestamp and a stale indicator. An older response cannot replace a newer cached edition.
- The public contract accepts only known source-link hosts, bounded text/metrics and citations referring to included source IDs. These checks do not prove semantic correctness; readers must still verify claims.
- Cache contents are public evidence, not model-training data. Platform retention/deletion requirements and operator approval remain part of production operations.

## Verification boundary

Automated tests exercise local public HTTP delivery, identical versions across readers, read-only routes, schedule execution, restart recovery, outage behavior, validation, and privacy isolation. External hosting, TLS/proxy setup, live API credentials, actual model synthesis and native desktop packaging remain operator/environment integration checks.
