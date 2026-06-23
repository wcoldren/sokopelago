-- Sokopelago POTD ratings. One rating per (date, level_n, visitor_id): the UNIQUE constraint +
-- INSERT OR IGNORE in the Worker drop casual duplicate-spam (one visitor flooding one puzzle) at
-- write time. The server never UPDATEs or DELETEs. No PII: `handle` is a self-chosen, non-personal
-- name.
CREATE TABLE IF NOT EXISTS ratings (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at    INTEGER NOT NULL,            -- server epoch ms (set by the Worker)
  schema         TEXT    NOT NULL,
  date           TEXT    NOT NULL,            -- UTC calendar day YYYY-MM-DD (the puzzle key)
  corpus         TEXT    NOT NULL,
  level_n        INTEGER NOT NULL,
  handle         TEXT    NOT NULL,
  visitor_id     TEXT    NOT NULL,            -- persisted, stable identity (display + spam dedup)
  session_id     TEXT    NOT NULL,
  solved         INTEGER NOT NULL,            -- 0/1
  attempts       INTEGER NOT NULL,
  moves          INTEGER NOT NULL,
  pushes         INTEGER NOT NULL,
  time_ms        INTEGER NOT NULL,
  used_hint      INTEGER NOT NULL,            -- 0/1
  fun            INTEGER NOT NULL,            -- 1..5
  difficulty     INTEGER NOT NULL,            -- 1..5
  client_version TEXT    NOT NULL,
  UNIQUE (date, level_n, visitor_id)          -- one rating per visitor per puzzle (spam dedup)
);

-- The GET /results aggregate filters by day.
CREATE INDEX IF NOT EXISTS idx_ratings_date ON ratings (date);

-- Unique visits per day: one row per (date, visitorId). POST /visit inserts OR IGNORE, so a
-- reload by the same visitor doesn't inflate the count. `uniqueVisitors` in GET /results is
-- COUNT(*) over this table for the day.
CREATE TABLE IF NOT EXISTS visits (
  date       TEXT    NOT NULL,
  visitor_id TEXT    NOT NULL,
  first_seen INTEGER NOT NULL,               -- server epoch ms (first time we saw this visitor today)
  PRIMARY KEY (date, visitor_id)
);
