---
name: fix-duplicate-onmounted-dual-startup
description: Fix Vue component mounted twice causing duplicate API calls and race conditions when onMounted/onUnmounted lifecycle hooks are accidentally defined twice in the same component
source: auto-skill
extracted_at: '2026-06-14T05:23:13.541Z'
---

## Problem
When a Vue SFC accidentally defines `onMounted()` or `onUnmounted` twice, Vue registers **both** callbacks. On component mount, they execute sequentially, causing the bootstrapped logic to run twice. This creates duplicate API calls, race conditions, and phantom errors (e.g., the first API call succeeds but the second `force: true` call cancels it, triggering false failure snapshots).

## Symptoms
- Duplicate log lines appearing at the same timestamp
- "Already started" or "Process exited with code 1" errors after a successful start
- Duplicate snapshot creation (e.g., two "final_R20" snapshots)
- Double resource allocation (two parallel engines, two polling loops)

## Detection
```bash
# Check for duplicate lifecycle hook definitions
grep -n "onMounted\|onUnmounted\|onBeforeMount" src/components/YourComponent.vue
# If grep returns 3+ matches (1 import + 2+ definitions), there's a duplicate
```

Or search within the file body for `onMounted(() => {` — there should be exactly **one** definition per lifecycle hook.

## Fix
Remove the duplicate block. In Vue SFCs, each lifecycle hook (`onMounted`, `onUnmounted`, `watch`, etc.) should be declared once. If the logic needs to be split, factor into a named function:

```vue
<script setup>
// ✅ Correct: single definition calling a named function
onMounted(() => {
  initComponent()
})

const initComponent = async () => {
  // all logic here
}
</script>
```

## When this commonly happens
- Merge conflicts that don't resolve duplicate blocks properly
- Copy-paste of lifecycle hooks from another component without removing the original
- Refactoring where the old definition wasn't cleaned up after moving logic to a different block

## Verification
After removing duplicates:
1. Run `grep -c "onMounted(() => {" file.vue` — should return exactly 1
2. Check the dev console for duplicate log entries at mount time
3. Monitor for no phantom errors after a successful initial operation
