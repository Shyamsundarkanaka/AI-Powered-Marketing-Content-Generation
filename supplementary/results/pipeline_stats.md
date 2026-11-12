## Job outcomes (since 1970-01-01 00:00:00)

- jobs: 23; completed: 9 (39%)
- failed - infrastructure: quota/rate limit: 8
- failed - validation exhaustion: 2
- failed - infrastructure: model not found: 1
- failed - infrastructure: store scrape (HTTP 429 rate limit / 404 stale URL): 2
- failed - infrastructure: provider 503 overloaded: 1
- end-to-end seconds (completed jobs): median 271.0 (IQR 238.0-281.0), n=9

## Stage completion time after pipeline start (seconds)

| stage | summary |
|---|---|
| campaign_brief | median 20.0 (IQR 14.0-29.0), n=13 |
| script | median 73.0 (IQR 54.0-90.5), n=11 |
| hashtags | median 79.5 (IQR 60.8-97.8), n=10 |
| caption | median 98.0 (IQR 86.2-111.8), n=10 |
| video_plan | median 92.0 (IQR 84.0-107.0), n=11 |
| voiceover | median 116.0 (IQR 100.0-130.0), n=9 |
| video_done | median 263.0 (IQR 220.0-279.0), n=9 |

- generated voiceover length (s): median 31.3 (IQR 28.2-33.9), n=9; video length (s): median 30.3 (IQR 26.4-33.5), n=9

## Validation retries per LLM node (jobs that reached that node)

| node | first-attempt OK | needed 2 attempts | needed 3 attempts | exhausted 3/3 (job failed) | executions |
|---|---|---|---|---|---|
| campaign_brief | 13 | 0 | 0 | 0 | 13 |
| script | 2 | 5 | 4 | 1 | 12 |
| hashtags | 10 | 0 | 0 | 0 | 10 |
| caption | 8 | 2 | 0 | 1 | 11 |
| video_plan | 10 | 1 | 0 | 0 | 11 |

- script retries logged: 9; 'beats must contain exactly 5 entries' = 7, spoken-length window = 2