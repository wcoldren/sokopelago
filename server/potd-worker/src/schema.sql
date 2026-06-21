-- Sokopelago POTD ratings — append-only. One row per submitted rating; the server never
-- UPDATEs or DELETEs (analysis dedups later by session_id + date + level_n). No PII: `handle`
-- is a self-chosen, non-personal name.
CREATE TABLE IF NOT EXISTS ratings (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at    INTEGER NOT NULL,            -- server epoch ms (set by the Worker)
  schema         TEXT    NOT NULL,
  date           TEXT    NOT NULL,            -- UTC calendar day YYYY-MM-DD (the puzzle key)
  corpus         TEXT    NOT NULL,
  level_n        INTEGER NOT NULL,
  handle         TEXT    NOT NULL,
  session_id     TEXT    NOT NULL,
  solved         INTEGER NOT NULL,            -- 0/1
  attempts       INTEGER NOT NULL,
  moves          INTEGER NOT NULL,
  pushes         INTEGER NOT NULL,
  time_ms        INTEGER NOT NULL,
  used_hint      INTEGER NOT NULL,            -- 0/1
  fun            INTEGER NOT NULL,            -- 1..5
  difficulty     INTEGER NOT NULL,            -- 1..5
  client_version TEXT    NOT NULL
);

-- The GET /results aggregate filters by day.
CREATE INDEX IF NOT EXISTS idx_ratings_date ON ratings (date);
