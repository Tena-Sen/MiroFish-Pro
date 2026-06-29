---
name: fix-missing-realtime-logs
description: Fix cases where frontend log console stays empty despite backend polling working, caused by disconnect between structured and console-style logging systems
source: auto-skill
extracted_at: '2026-06-12T02:00:00.000Z'
---

# Fix Missing Real-Time Logs in Frontend Console

When the frontend log console (e.g., a `console-logs` panel showing real-time backend output) stays empty or shows no new content, the root cause is typically a disconnect between the structured logging system and the console-style logging system.

## Symptom

- Frontend polls `/api/.../console-log` at regular intervals (e.g., every 1.5s)
- API returns `{"success": true, "data": {"logs": [], ...}}` — always empty
- Structured logs (e.g., `agent_log.jsonl`) ARE being written correctly
- The backend has both a `ReportConsoleLogger` (or equivalent) and a `ReportAgentLogger` but the console logger never receives any data

## Root Cause Pattern

The architecture has **two independent logging systems** that serve different purposes:

1. **Structured JSON logger** (e.g., `ReportLogger`) — writes `agent_log.jsonl`, each entry is a structured JSON object with action, stage, details. This is consumed by the frontend for the workflow UI (progress steps, generated sections, etc.)

2. **Console-style logger** (e.g., `ReportConsoleLogger`) — writes `console_log.txt`, plain text lines like `[19:46:14] INFO: search complete: found 15 results`. This is consumed by the frontend for the "console output" panel at the bottom.

**The bug**: The console logger is initialized (FileHandler attached to a logging module), but the business logic ONLY calls the structured logger's `log_*` methods. No code ever calls Python's `logging.getLogger(...).info()`, so the console file stays empty.

```python
# Initialization — both loggers are created
self.report_logger = ReportLogger(report_id)      # writes agent_log.jsonl
self.console_logger = ReportConsoleLogger(report_id)  # attaches FileHandler to logging module

# Business logic — ONLY uses structured logger
self.report_logger.log_start(...)        # writes JSON only, never triggers console
self.report_logger.log_planning_complete(...)  # same
self.report_logger.log_section_complete(...)       # same

# console_log.txt stays EMPTY because nobody calls:
# logging.getLogger('mirofish.report_agent').info(...)
```

## Fix Procedure

### Step 1: Confirm Both Logging Systems Exist

Search for two logger classes:
```bash
grep -rn "class.*Logger" backend/app/services/
```

Verify one writes structured JSON (`.jsonl`) and the other writes plain text (`.txt`).

### Step 2: Trace the Write Path

Check which logger the business logic actually calls:
```bash
grep -n "self\.report_logger\.log_" backend/app/services/report_agent.py
```

If all calls are to `report_logger` and none to `console_logger` or `logging.info()`, the console log is disconnected.

### Step 3: Bridge the Two Loggers

In the structured logger's `log()` method, after writing JSON, also emit to Python's logging module so the console logger's FileHandler catches it:

```python
# In ReportLogger.log() method, after the JSONL write:

with open(self.log_file_path, 'a', encoding='utf-8') as f:
    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

# ALSO write to console logger via Python logging module
section_info = f"[{section_title}]" if section_title else ""
console_msg = f"{log_entry.get('timestamp', '')} INFO: {action} - {json.dumps(details, ensure_ascii=False)}"
logging.getLogger('mirofish.report_agent').info(f"{section_info} {console_msg}")
```

**Key prerequisite**: Ensure `import logging` is at the top of the file.

### Step 4: Verify the Console File Gets Data

```bash
# After starting a report, check:
cat backend\uploads\reports\{report_id}\console_log.txt
# Should have lines like:
# [19:46:14] INFO: 2026-06-12T19:46:14.123456 INFO: report_start - {"simulation_id": "sim_xxx", ...}
```

### Step 5: Verify Frontend Receives Data

```bash
curl http://127.0.0.1:5001/api/report/{report_id}/console-log
# Should return logs array with content
```

## Alternative: If You Only Need One Logger

If the two systems are not strictly needed separately, consider consolidating:

- Keep only the structured JSON logger
- Have the frontend parse the JSONL file directly for both workflow state and console display
- Remove the console logger entirely

This reduces maintenance burden but requires frontend changes.

## Frontend-Side Checks

If the backend fix doesn't resolve the issue, check:

1. **Component visibility**: Is the log panel hidden by CSS (`width: 0%`, `opacity: 0`) when using certain view modes?
2. **Container height**: Is `.log-content` height set to a visible value (e.g., `100px`)?
3. **Polling timer**: Check `consoleLogTimer` is not `null` in the debugger
4. **Cooldown anti-pattern**: If `CONSOLE_LOG_COOLDOWN` is too high, logs may appear to lag
5. **Component lifecycle**: If the view uses `v-if` instead of `v-show`, component destruction clears `consoleLogs`

## Key Takeaway

> **Never initialize a parallel logging system without ensuring the business logic actually uses it.** When you have both structured and console loggers, the structured logger's core `log()` method is the right place to bridge them — write once, emit to both outputs.
