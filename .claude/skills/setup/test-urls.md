# TLDL self-test URLs

Canonical URLs the setup skill calls `get_transcript` against in Phase 5 and Phase 8. For each, the expected fields appear in the returned markdown's YAML frontmatter.

- **YouTube** — `https://www.youtube.com/watch?v=RaKFP_DuqpA`
  - expected `source: youtube`
  - long-form real podcast — exercises the paragraph coalescer over a non-trivial transcript.

- **Spotify → YouTube** — `https://open.spotify.com/episode/1cXQalDxiGgptzM1nC7SCh?si=d5148f9e6a2249a6`
  - expected `source: spotify-via-youtube`
  - expected `match_confidence` >= 0.5
  - exercises the Spotify oEmbed → YouTube search → rapidfuzz scoring path. The `?si=` tracking param is intentionally preserved to confirm the URL parser ignores extraneous query strings.

- **Apple → YouTube** — `https://podcasts.apple.com/us/podcast/the-diary-of-a-ceo-with-steven-bartlett/id1291423644?i=1000753955113`
  - expected `source: apple-via-youtube`
  - expected `match_confidence` >= 0.5
  - exercises the iTunes Lookup → YouTube search path. *Diary of a CEO* posts both audio (Apple) and video (YouTube), so resolution should succeed.
  - **Stability caveat**: the iTunes Lookup window is "most recent 200 episodes per show". *Diary of a CEO* posts ~3×/week, so this episode will fall out of the lookup window in roughly 4–5 months. If this test starts returning "out of lookup window," replace this URL with a more recent episode (or pick a less-frequent podcast). The skill should diagnose this failure mode for the user rather than treating it as a code bug.

- **Error path** — `https://example.com/foo`
  - expected: `ToolError` with message starting `"Unsupported URL"`
  - confirms the URL detector rejects non-podcast URLs cleanly (no stack trace).
