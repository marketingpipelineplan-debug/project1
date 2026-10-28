# Reddit research and adaptive creator memory

Implemented 13 October 2026. This feature adds fresh research and evidence-based recommendations. It does **not** fine-tune model weights or train on Reddit content.

## Configure Reddit locally

Use approved Reddit API access for this application's use case. The app uses read-only OAuth endpoints on `oauth.reddit.com` and the token-refresh endpoint on `www.reddit.com`. It never asks for your Reddit password or falls back to scraping.

Configure these environment variables in the same terminal that starts `npm run dev`:

- `GOODFORM_REDDIT_ACCESS_TOKEN`: an OAuth token with `read` scope.
- `GOODFORM_REDDIT_USER_AGENT`: a descriptive user agent identifying your approved application/version and contact, as required by Reddit.

For renewable access, configure these **instead of** the access-token variable:

- `GOODFORM_REDDIT_CLIENT_ID`
- `GOODFORM_REDDIT_REFRESH_TOKEN`
- `GOODFORM_REDDIT_CLIENT_SECRET` for a confidential client; leave absent for an approved installed/public client.
- `GOODFORM_REDDIT_USER_AGENT`

The access token takes precedence when both modes are configured. Keep credentials in local environment variables or a local secret manager. Do not commit them or paste them into the chat. `.env` files are not automatically loaded. Restart the API after configuration. In PowerShell, environment variables use `$env:VARIABLE_NAME`; in zsh, use `export VARIABLE_NAME` after setting its value locally. These variables must be inherited by the application process.

The application reads configuration without exposing token values through its API. Tokens are not stored in SQLite. Refresh uses the configured refresh token; interactive OAuth registration/consent is not implemented here. Production distribution still needs a managed OAuth setup and the required Reddit authorization for its use.

Official references: [API documentation](https://www.reddit.com/dev/api/), [Data API terms](https://redditinc.com/policies/data-api-terms), [Developer terms](https://redditinc.com/policies/developer-terms).

## Use the trend desk

1. Open **Trend desk** and enter 1–3 relevant community names, without `r/`. `popular` is available for a broad starting point.
2. Choose hot, rising or top-of-day. Each requested feed returns up to 20 entries.
3. Inspect the actual source links, net scores, comment counts, age and collection timestamp.
4. Select **Create ideas with this research**, then choose Video, Reel, Tweet or Livestream. Alternatively enable **Research Reddit before drafting** in the normal creation dialog.
5. Generate with an installed local Ollama model, or explicitly choose a rule-based template. Every result starts pending human review.

`research_reddit_trends` is a controlled read-only tool invoked by the application pipeline on the creator's request. The model receives its results as untrusted research data. This is not an unrestricted browsing agent and does not require the model to invent API URLs. Creator analytics and profile details are never sent to Reddit; only the requested feeds and API credentials are sent.

The signal score ranks a **single selected feed sample** using `log(1 + positive net score / age_hours) + 0.7 × log(1 + comments / age_hours)`, with age floored at one hour, followed by a midrank percentile. It is not a platform-wide trend estimate, measured acceleration or a prediction of a creator's success. Pinned, adult, removed, malformed, future-dated and older-than-seven-day posts are excluded.

Repeated identical requests use a 15-minute in-memory cache; new requests have a 30-second cooldown. Results are not persisted as a raw Reddit corpus. Drafts retain source IDs/URLs and collection time; generated prose may quote or adapt a short title. There is no fine-tuning dataset export. Deletion synchronization, production retention controls and licensing obligations must be resolved before distribution.

## Close the learning loop

1. Generate an idea and complete the existing human review/approval process.
2. Open **Learning journal**. Choose that exact approved version, platform, format, a single factor, a hypothesis, primary metric, observation window and target lift.
3. Import baseline posts **before planning**. The plan freezes the available comparison snapshots; later data cannot silently improve the comparison group.
4. Publish yourself. Import its analytics with a stable ID and accurate timestamps, then link that publication to the plan.
5. Import subsequent snapshots. Results automatically use the selected 24-, 48- or 168-hour window, within one hour. Later lifetime views never replace the original target window.
6. Future ideas automatically include matching platform/format memory: wins, losses, sample count, median lift, the tested hypotheses and supporting measurements. The template also reports the applicable memory; the local model can interpret it in greater detail.

A completed experiment is above target only when the primary metric reaches the predeclared relative improvement over the median of at least three earlier matching-platform/format/window posts. Retention and engagement lift is relative percent, not percentage-point difference. Engagement in the journal consistently uses `(likes + comments) / views`; the original library score also includes available shares and is a separate heuristic.

Only one experiment can count a given publication. Unknown metrics, zero baselines and missing time windows remain unevaluated, not failures. A draft edited after planning cannot be linked using an obsolete approval. Historical reviews are explicitly labeled and excluded from adaptive memory because their hypothesis was recorded after publication. Prospective and retrospective counts are shown separately through the API.

Supporting measurements can compare retention, CTR, average watch time, followers gained, saves, dislikes and peak live viewers when supplied for the outcome and at least three baseline posts. These are observations, not a causal answer to “why.” The UI preserves the hypothesis and flags alternative explanations such as topic, title, thumbnail, duration, timing, paid promotion and audience changes. Future recommendations remain experiments, not guarantees.

## Data model and limits

- `observations`: immutable timestamped analytics, de-duplicated by workspace/platform/post/timestamp. Conflicting reimports at one timestamp are rejected atomically. Importing older observations does not roll back the latest library snapshot.
- `experiments`: frozen approved draft identity, hypothesis, primary success criterion, eligible baseline snapshots, linked publication identity and prospective/historical classification.
- Adaptive patterns are recomputed from those records, including failed tests. Grouping includes platform, format, metric, observation window, target lift and tested factor. Groups with fewer than five experiments are labeled tentative; five does not imply statistical significance.
- The database currently assumes one creator account per platform per workspace. Account-level separation must be added before supporting multiple accounts on the same platform.
- Counts, retention, CTR and live metrics need consistent platform definitions supplied by the creator/import adapter. Duration, paid amplification, seasonality and audience size are not yet matched statistically.
- Trend research requires internet and Reddit authorization. Analysis and generation remain local. An installed model is required for AI prose; no hosted-model fallback exists.

## Universal Trend desk (14 October 2026)

The Trend desk now requests `/api/trends/briefing`: a general public briefing independent of creator profiles, analytics and learning memory. The endpoint collects the available public feed, then requests a source-grounded summary from local Ollama using `GOODFORM_TREND_MODEL` (default `qwen3:8b`). It rejects remote model aliases and returns explicit coverage/availability instead of fabricating a summary when research or inference is unavailable.

The universal briefing now has public adapters for Reddit, YouTube, X, Twitch and Kick, each requiring approved access. See [public-trends.md](public-trends.md) for configuration, coverage limits and remaining integrations. Per-community Reddit research remains available separately for drafting. A hosted collection/synthesis service is still needed to distribute identical results across devices. No model-weight updates, autonomous planning loop or reinforcement-learning policy is implemented.
