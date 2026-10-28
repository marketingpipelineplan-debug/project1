# Analytics import v1

JSON: an array of post objects. CSV: one header row followed by posts. At most 1,000 records and 1.5 MB of UTF-8 input per import. All rows are validated before any row is saved.

Required fields:

| Field | Meaning |
| --- | --- |
| `title` | 1–300 characters |
| `platform` | Exact platform name shown in Connections |
| `format` | Consistent label such as Video, Reel, Short, Post, Stream |
| `published_at` | ISO date/datetime; date-only values use UTC |
| `views` | Nonnegative integer |
| `likes` | Nonnegative integer |
| `comments` | Nonnegative integer |

Optional fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable platform post ID; otherwise derived from platform/title/publication date |
| `shares` | Nonnegative integer; empty means unavailable |
| `retention` | Average percentage viewed/completion proxy, 0–100; empty means unavailable. Do not mix definitions within a cohort. |
| `observed_at` | ISO observation timestamp; defaults to import time |
| `observation_hours` | Hours between publication and observation; must match the supplied dates within one hour. Leave unknown if not established. |
| `comment_samples` | JSON only: up to 100 strings, 2,000 characters each |

No API tokens, passwords or private contact details belong in these files. Records with the same platform/id preserve timestamped history; only newer observations update the latest snapshot. A conflicting reimport at the same observation timestamp is rejected. IDs from different platforms are separate. Duplicate platform/id pairs within one import are rejected.

Scoring requires at least three positive-view records with identical platform, format and observation window. A score combines 50% views percentile and 50% engagement-rate percentile. It is a transparent prototype heuristic, not a statistically calibrated prediction. Unknown values are displayed as unavailable; zero-view engagement is undefined. Duration, paid amplification, audience size and seasonal context are not yet controlled.

## Additional optional measurements

`ctr` is a supplied percentage (0–100). `avg_watch_seconds` and `duration_seconds` are nonnegative numbers. `followers_gained`, `saves`, `dislikes` and `peak_live_viewers` are nonnegative integers. `topic` and `hook` are optional short labels (up to 300 characters) passed as creator context. Leave metrics unavailable when the platform does not provide them. Match the platform’s metric definitions across compared posts; these are not universally interchangeable.

The Learning journal uses immutable observations and requires matching platform, format and target window. It also requires at least three earlier baseline posts. See [the feedback-loop guide](reddit-and-learning.md).
