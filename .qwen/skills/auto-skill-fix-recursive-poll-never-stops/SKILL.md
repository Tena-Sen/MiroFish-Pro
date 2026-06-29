---
name: fix-recursive-poll-never-stops
description: Fix recursive setTimeout polling that never terminates because .then callback always schedules a new timer even after completion and stopPolling()
source: auto-skill
extracted_at: '2026-06-14T07:15:00.000Z'
---

# Fix Recursive setTimeout Polling That Never Stops

When a polling mechanism uses recursive `setTimeout` (instead of `setInterval`), the `.then` callback that schedules the next iteration is **always** called when the fetch resolves — even after `stopPolling()` has already cleared the timer. This creates a perpetual loop where each fetch resolves, `.then` runs, and schedules a brand new timer, overriding the previous `stopPolling()` call.

## The Bug Pattern

```javascript
// ❌ BROKEN: .then always schedules a new timer
const startStatusPolling = () => {
  const poll = () => {
    fetchRunStatus().then(() => {
      const interval = getDynamicInterval()
      statusTimer = setTimeout(poll, interval)  // ← New timer even after stopPolling!
    })
  }
  poll()
}

const stopPolling = () => {
  if (statusTimer) {
    clearTimeout(statusTimer)
    statusTimer = null
  }
}

const fetchRunStatus = async () => {
  // ... fetch logic ...
  if (isCompleted) {
    phase.value = 2
    stopPolling()  // ← Clears the OLD timer
    return
  }
}
```

### Execution Flow

```
1. poll() calls fetchRunStatus()  (timer #1)
2. fetchRunStatus resolves (completed) → stopPolling() clears timer #1
3. fetchRunStatus Promise resolves
4. .then callback runs → creates timer #2
5. poll() called again → fetchRunStatus → stopPolling() clears timer #2
6. .then callback runs → creates timer #3
... infinite loop ...
```

The problem: `stopPolling()` clears the **old** timer, but `.then` creates a **new** one. They don't cooperate.

## Fix: Use Return Value to Guard Timer Scheduling

```javascript
// ✅ FIXED: .then checks return value before scheduling next poll
const startStatusPolling = () => {
  const poll = () => {
    fetchRunStatus().then((completed) => {
      if (!completed) {  // ← Only schedule next poll if still running
        const interval = getDynamicInterval()
        statusTimer = setTimeout(poll, interval)
      }
    })
  }
  poll()
}

const fetchRunStatus = async () => {
  if (isCompleted) {
    phase.value = 2
    stopPolling()
    return true  // ← Tell .then to NOT schedule another poll
  }
  return false  // ← Still running, .then will schedule next poll
}
```

### Execution Flow After Fix

```
1. poll() calls fetchRunStatus()  (timer #1)
2. fetchRunStatus detects completion → stopPolling() clears timer #1 → returns true
3. fetchRunStatus Promise resolves
4. .then callback runs with (completed=true) → if (!true) is false → NO new timer
5. Polling stops permanently ✅
```

## Related: Also Handle Error Actions

When the backend reports an error (e.g., `error` action in agent logs), the frontend must also detect it and stop polling. Missing this causes the same perpetual loop when the task fails instead of succeeds.

```javascript
// In fetchAgentLog (Step4Report.vue), handle both completion and error:
if (log.action === 'report_complete') {
  isComplete.value = true
  emit('update-status', 'completed')
  stopPolling()
}

if (log.action === 'error') {
  isComplete.value = true
  emit('update-status', 'error')
  stopPolling()  // ← MUST also stop on error!
}
```

## When This Pattern Occurs

1. **Dynamic interval polling** — When interval varies based on state (e.g., faster polling in early rounds, slower in later rounds), developers often use recursive `setTimeout` instead of `setInterval`
2. **Status polling** — Checking API status endpoints (simulation status, report status, task progress)
3. **Copy-paste errors** — When copying a polling pattern, the `.then` scheduling logic is often overlooked as something that "just works"

## Checklist

When debugging a "polling never stops" issue with recursive `setTimeout`:

1. Check if `.then` callback always schedules a new timer regardless of completion state
2. Verify `stopPolling()` clears the timer but doesn't prevent `.then` from creating a new one
3. Fix by making `fetchRunStatus` return a boolean flag
4. Make `.then` only schedule the next poll if the fetch reports "not completed"
5. Ensure error/failure states also return `true` to stop the poll chain
6. Test: complete a task, verify logs stop immediately, no further API requests

## Key Takeaway

> **`.then` is unconditional.** It runs whenever the Promise resolves, regardless of what happened inside the async function. If you `return` early after `stopPolling()`, the `.then` callback still executes. You must explicitly pass a signal (boolean return value, or check a state flag) to prevent `.then` from creating a new timer.
