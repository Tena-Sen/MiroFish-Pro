---
name: fix-cooldown-undefined-var
description: Fix frontend log polling silently broken when a cooldown variable used in fetchInterval function is never declared (const/let/var), causing ReferenceError that crashes the entire fetch function
source: auto-skill
extracted_at: '2026-06-14T03:54:56.081Z'
---

# Fix Missing Real-Time Logs Caused by Undeclared Cooldown Variable

When adding an "anti-spam" cooldown to a periodic fetch/poll function in the frontend, a variable may be referenced in the cooldown check condition but never declared. This causes a `ReferenceError` in strict mode (Vue SFC default), which **crashes the entire fetch function** — the API call never executes, and the log panel stays permanently empty.

## Symptom

- Frontend component polls an API at regular intervals (e.g., `setInterval(fetch, 1500)`)
- The function contains a cooldown check like `if (now - lastLogTime < COOLDOWN) return`
- The API endpoint works fine (confirmed via curl or dev tools network tab)
- Log panel is permanently empty or never shows new content
- **No JavaScript error visible** in many cases because the error is thrown synchronously during function execution but not caught (the interval silently fails)
- The variable in the cooldown check (`lastLogTime`, `lastConsoleLogTime`, etc.) is referenced but never declared with `const`/`let`/`var`

## Root Cause Pattern

```javascript
// A cooldown optimization was added to reduce API calls when logs are empty

let lastAgentLogTime = 0
const AGENT_LOG_COOLDOWN = 3000
const CONSOLE_LOG_COOLDOWN = 3000

// ✅ Correctly uses lastAgentLogTime (declared above)
const fetchAgentLog = async () => {
  const now = Date.now()
  if (now - lastAgentLogTime < AGENT_LOG_COOLDOWN) return  // OK
  // ... rest of function
}

// ❌ BUG: lastConsoleLogTime is NEVER declared!
const fetchConsoleLog = async () => {
  const now = Date.now()
  if (now - lastConsoleLogTime < CONSOLE_LOG_COOLDOWN) return  // ReferenceError!
  // This line never executes. The entire function crashes.
}
```

In strict mode (`.vue` SFC `<script setup>` is strict), accessing an undeclared variable throws `ReferenceError` immediately. The error is not caught by the surrounding `try/catch` because it happens **before** the `try` block (in the cooldown check).

## Fix Procedure

### Step 1: Identify the Undeclared Variable

Look at the cooldown check condition:
```javascript
if (now - lastConsoleLogTime < CONSOLE_LOG_COOLDOWN) return
```

Search for the variable declaration in the same file:
```bash
grep -n "lastConsoleLogTime" frontend/src/components/Step4Report.vue
```

If it appears only in the `if` condition but nowhere in a `let`/`const`/`var` declaration, it's the bug.

### Step 2: Declare the Variable

Add the missing declaration alongside the other cooldown variables:

```javascript
let lastAgentLogTime = 0          // already exists
let lastConsoleLogTime = 0        // ← ADD THIS LINE
const AGENT_LOG_COOLDOWN = 3000
const CONSOLE_LOG_COOLDOWN = 3000
```

### Step 3: Ensure the Variable Is Updated After Each Successful Fetch

Don't forget to update the cooldown timestamp after a successful fetch, otherwise the cooldown will never expire:

```javascript
const fetchConsoleLog = async () => {
  if (!props.reportId) return
  const now = Date.now()
  if (now - lastConsoleLogTime < CONSOLE_LOG_COOLDOWN) return

  try {
    const res = await getConsoleLog(props.reportId, consoleLogLine.value)
    if (res.success && res.data) {
      // ... process logs ...
    }
    lastConsoleLogTime = Date.now()  // ← ADD THIS LINE
  } catch (err) {
    console.warn('Failed to fetch console log:', err)
  }
}
```

### Step 4: Verify

- Check that the cooldown check now works correctly (no ReferenceError)
- Check that the variable is updated after each successful response
- In browser DevTools console, verify no `ReferenceError: lastConsoleLogTime is not defined`

## Prevention Checklist

When adding a cooldown to a polling function:

1. **Declare the variable** at module scope with `let` (needs to be mutable)
2. **Use it in the cooldown check** before the `try` block
3. **Update it in the success path** inside the `try` block
4. **Match the pattern**: both `fetchAgentLog` and `fetchConsoleLog` should have identical cooldown patterns — if one has it and the other doesn't, review whether it was intentional or accidental omission

## Key Takeaway

> **Adding a cooldown check references a variable. Declaring the variable is not optional.** When copy-pasting a cooldown pattern from one function to another, double-check that every variable used in the check is actually declared. The error is subtle because it happens at module load time, not at runtime — but if the function is never called until a user action, you might miss it during initial testing.
