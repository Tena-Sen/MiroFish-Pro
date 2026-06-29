---
name: diagnose-backend-polling-loop
description: Systematically diagnose "backend continuously refreshing/looping" issues in full-stack apps with frontend polling
source: auto-skill
extracted_at: '2026-06-11T15:38:25.788Z'
---

# Diagnose Backend Polling Loop

When a user reports that the backend is "continuously refreshing", "stuck in a loop", or producing non-stop log output, follow this systematic investigation approach.

## Step 1: Clarify the Symptom

Ask what "loop" means specifically:
- Backend console logs scrolling continuously?
- API requests repeating in network tab?
- Process restarting / hot-reload cycling?
- An actual infinite loop in business logic?

## Step 2: Check Backend Entry Point & Middleware

1. Read the app factory / startup file (e.g., `app/__init__.py`, `main.py`)
2. Look for `before_request` / `after_request` middleware that logs every request — this amplifies perceived noise
3. Check if `debug=True` is set (Flask reloader spawns child processes, doubling output)
4. Check logging level — `DEBUG` level will show every request even if not explicitly logged

## Step 3: Search Frontend for Polling Mechanisms

Use an Explore subagent to thoroughly search the frontend source for:
- `setInterval` — most common polling pattern
- `setTimeout` used recursively
- `refetch`, `polling`, `poll` keywords
- Axios/fetch interceptors with retry logic
- WebSocket reconnection loops

For each polling source found, document:
- File and line
- Interval duration
- Which API endpoint it calls
- Start/stop conditions (when does it begin? does it ever stop?)

## Step 4: Identify Lifecycle Bugs

Common bugs that cause "infinite" polling:
1. **Polling never stops on completion** — timer not cleared when task reaches `completed`/`failed` state
2. **Polling never stops on unmount** — `onUnmounted` / `useEffect` cleanup missing
3. **Multiple timers stacking** — starting a new timer without clearing the old one
4. **Duplicate components** — same polling logic in multiple views that may mount simultaneously
5. **Cooldown anti-pattern** — `setInterval` fires every 2s but callback checks "3s cooldown" and skips; the interval itself should be 3s

## Step 5: Quantify the Load

Build a table of all concurrent polling sources and their frequencies. Example:

| Source | Interval | Endpoint |
|--------|----------|----------|
| Component A | 2s | /api/status |
| Component B | 3s | /api/profiles |

Calculate worst-case requests/second. Even 2-3 req/s will make a backend with request logging appear to be "constantly refreshing".

## Step 6: Recommend Fixes

Prioritized:
1. **Stop polling on completion** — most impactful fix
2. **Consolidate duplicate pollers** — merge overlapping timers
3. **Increase intervals** — 2s → 5s is usually acceptable for status checks
4. **Use WebSocket/SSE** for true real-time needs instead of polling
5. **Reduce backend log verbosity** — move request logging to DEBUG level, not INFO
