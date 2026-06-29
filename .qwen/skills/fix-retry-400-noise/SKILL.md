---
name: fix-retry-400-noise
description: Fix misleading repeated error logs caused by retrying on 4xx server errors instead of network-only failures
source: auto-skill
extracted_at: '2026-06-12T03:00:00.000Z'
---

# Fix Retry-on-4xx Error Noise and Missing Environment State Checks

When a user reports repeated error logs (e.g., 3 identical 400 requests) or confusing error messages, the root cause is often an overly aggressive retry mechanism combined with missing user-facing error descriptions.

## Symptom Patterns

1. **Repeated 4xx logs**: Backend shows multiple identical `POST /api/... 400` lines in the same second, caused by `requestWithRetry` retrying on HTTP errors instead of only network failures.
2. **Generic error messages**: User sees "Request failed" instead of a specific reason like "Simulation environment not running".
3. **Silent failures**: Frontend catches an error but doesn't explain *why* the operation failed in actionable terms.

## Root Cause Pattern

```javascript
// BEFORE — retries on ALL errors including 400/500
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error  // retries even on 400!
      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}
```

When the API returns `{ success: false, error: "envNotRunning" }` with HTTP 400, `axios` throws an error with `error.response` set. The retry loop treats this as a transient failure and retries, producing 3 identical 400 logs.

## Fix Procedure

### Step 1: Fix the Retry Logic — Only Retry Network Errors

In `requestWithRetry`, check for `error.response` (axios sets this for HTTP errors):

```javascript
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      // Don't retry on HTTP errors (4xx, 5xx) — only network errors
      if (error.response) {
        return Promise.reject(error)
      }
      // Retry only on network failures (connection refused, timeout, etc.)
      if (i === maxRetries - 1) throw error
      console.warn(`Request failed (network error), retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}
```

### Step 2: Detect and Surface Specific Error Types in Vue Components

Add error type detection functions in the component:

```javascript
const isEnvNotRunningError = (errorMsg) => {
  if (!errorMsg) return false
  const msg = errorMsg.toLowerCase()
  return msg.includes('envNotRunning') ||
         (msg.includes('环境') && msg.includes('运行')) ||
         (msg.includes('environment') && (msg.includes('not running') || msg.includes('not run')))
}

const sendToAgent = async (message) => {
  // ... validation ...
  const res = await interviewAgents({ simulation_id: props.simulationId, interviews: [...] })
  
  if (!res.success) {
    const errorMsg = res.error || t('step5.requestFailed')
    if (isEnvNotRunningError(errorMsg)) {
      throw new Error(t('step5.envNotRunningUser', { error: errorMsg }))
    }
    throw new Error(errorMsg)
  }
  // ... success handling ...
}
```

### Step 3: Add i18n Keys for Specific Error Messages

Add user-friendly translations in `locales/zh.json` and `locales/en.json`:

```json
// zh.json (under step5 section)
"envNotRunningUser": "模拟环境未运行：{error}",
"envNotRunning": "模拟环境未运行或已关闭，无法发送采访请求。请先启动模拟环境。"
```

### Step 4: Add Guards for Missing Prerequisite Data

When a component depends on asynchronously-loaded data (e.g., `simulationId` from `loadReportData()`), add null checks in every function that uses that data:

```javascript
const sendToAgent = async (message) => {
  if (!props.simulationId) {
    addLog(t('log.noSimulationId'))
    return
  }
  // ... proceed with request ...
}
```

**Apply this pattern to every async function** that uses the reactive prop, not just one or two.

## Common Error Conditions to Check For

| Error Condition | Check Pattern | Typical HTTP Code |
|----------------|---------------|-------------------|
| Missing simulation_id | `if (!simulation_id)` | 400 |
| Missing required list | `if (!interviews || !Array.isArray(interviews))` | 400 |
| Environment not running | `if not check_env_alive(simulation_id)` | 400 |
| Invalid platform | `if platform not in ("twitter", "reddit")` | 400 |
| Agent not selected | `if (!selectedAgent)` | Frontend, throw |

## Verification

1. Trigger the same error scenario again — should see **only 1 log line** (no retries on 400)
2. The error message should be **specific and actionable** (not just "Request failed")
3. Check that all entry points into the API use null checks for prerequisite data

## Key Takeaway

> **Retry should only apply to transient failures (network errors, timeouts), not to semantic failures (400, validation errors, environment not ready). And every API call should surface a specific, user-actionable error message — not a generic "request failed".**
