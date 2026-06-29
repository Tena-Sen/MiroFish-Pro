---
name: fix-simulation-restore-choice-dialog
description: Add a user-facing choice dialog when restoring a snapshot, letting users choose between resuming from the snapshot or starting fresh from the beginning
source: auto-skill
extracted_at: '2026-06-14T09:28:41.565Z'
---

## Problem
When restoring a snapshot, the default behavior was to immediately proceed with restoration. Users wanted the option to either:
1. Restore and resume from the snapshot's saved round (continue)
2. Restore the files but start fresh from round 0 (start over)

This is a UX pattern for giving users **choices between multiple actions** when a potentially destructive or irreversible operation is about to happen.

## Root Cause
The original implementation called `handleRestoreSnapshot()` directly, which immediately triggered the restore process. No decision point was provided to the user.

## Solution: Two-Stage Restore

### Step 1: Add State Variables
In the component, add refs to track the restore choice:

```javascript
const showRestoreChoice = ref(false)
const restoreMode = ref('restore-resume') // 'restore-resume' or 'restore-startover'
const pendingSnapshotName = ref('')
```

### Step 2: Intercept the Restore Action
Modify `handleRestoreSnapshot` to show a choice dialog instead of proceeding:

```javascript
const handleRestoreSnapshot = async (snapshotName) => {
  pendingSnapshotName.value = snapshotName

  // Check if snapshot has a saved round number
  const snap = snapshots.value.find(s => s.name === snapshotName)
  const savedRound = snap?.current_round ?? 0

  if (savedRound > 0) {
    // Show choice dialog — user can pick resume or startover
    showRestoreChoice.value = true
  } else {
    // No round info, just restore
    doRestoreSnapshot('restore-startover')
  }
}
```

### Step 3: Add Choice Dialog Template
In the template, add an overlay dialog with two radio options:

```vue
<div v-if="showRestoreChoice" class="restore-choice-overlay">
  <div class="restore-choice-dialog">
    <h3>选择快照恢复模式</h3>
    <p v-if="pendingRound" class="restore-choice-hint">
      检测到快照中包含第 {{ pendingRound }} 轮的数据，请选择恢复方式
    </p>
    <div class="restore-choice-options">
      <label class="restore-choice-option">
        <input type="radio" v-model="restoreMode" value="restore-resume" />
        <span class="option-label">从快照节点继续（第 {{ pendingRound }} 轮）</span>
      </label>
      <label class="restore-choice-option">
        <input type="radio" v-model="restoreMode" value="restore-startover" />
        <span class="option-label">恢复文件但从头开始（第 0 轮）</span>
      </label>
    </div>
    <div class="restore-choice-actions">
      <button class="btn-cancel" @click="showRestoreChoice = false">取消</button>
      <button class="btn-confirm" @click="doRestoreSnapshot(restoreMode)">确认恢复</button>
    </div>
  </div>
</div>
```

### Step 4: Separate Confirm from Cancel
The `doRestoreSnapshot` method now receives the mode:

```javascript
const doRestoreSnapshot = async (mode) => {
  showRestoreChoice.value = false
  if (!pendingSnapshotName.value) return

  try {
    const res = await restoreSnapshot(simulationId.value, {
      snapshot_name: pendingSnapshotName.value
    })
    if (res.success) {
      addLog(t('log.snapshotRestored', { name: pendingSnapshotName.value }))
      // If mode is restore-resume, start with start_round
      if (mode === 'restore-resume') {
        await doStartSimulation({ start_round: true })
      }
      // If mode is restore-startover, normal start
      else {
        await doStartSimulation({})
      }
    }
  } catch (err) {
    addLog(t('log.snapshotRestoreFailed', { error: err.message }))
  } finally {
    pendingSnapshotName.value = ''
  }
}
```

### Step 5: Add CSS Styling — Use `position: fixed` for overlays

**Critical**: When the overlay is a child of a container with `max-height` and `overflow-y: auto`, `position: absolute` will clip the overlay to that container's viewport. Use `position: fixed` instead so it covers the entire browser viewport.

```css
.restore-choice-overlay {
  position: fixed;  /* NOT absolute — parent may have overflow/height constraints */
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;  /* Ensure above all page elements */
  animation: fadeInOverlay 0.2s ease;
}
```

**Dialog styling tips:**
- Use `position: fixed` + `z-index: 9999` + `backdrop-filter: blur` for the overlay
- Dialog container: `border-radius: 12px`, `padding: 28px 32px`, `min-width: 420px`, `max-width: 500px`, `width: 90vw`
- Add entrance animation: `@keyframes slideUpDialog { from { opacity: 0; transform: translateY(20px) scale(0.96); } to { opacity: 1; transform: translateY(0) scale(1); } }`
- Option cards: `padding: 14px 16px`, `border: 1.5px solid #E8E8E8`, `border-radius: 8px`, `background: #FAFAFA`, hover with `border-color: #409EFF` + `background: #F0F7FF`
- Radio buttons: set `accent-color: #409EFF`, `width: 16px`, `height: 16px`
- Buttons: `padding: 8px 20px`, `border-radius: 6px`, `min-width: 72px`, `font-size: 14px`

## Key Design Decisions
1. **Overlay vs modal**: Use a full-screen overlay (`position: fixed` covering the viewport) rather than `position: absolute` scoped to the component. Parent containers often have `max-height` + `overflow-y: auto` which clips absolute-positioned children.
2. **Default selection**: The "resume from snapshot" option is selected by default since that's the more intuitive choice for most users.
3. **Only show when applicable**: The dialog only appears if the snapshot has a `current_round > 0`. Snapshots from brand-new simulations (round 0) skip the choice.
4. **Start round propagation**: When choosing "resume", `start_round` is passed to `doStartSimulation`, which flows through the API to the backend's `--start-round` argument.

## Why This Pattern Is Reusable
This two-stage choice dialog pattern (intercept action → show options → execute based on choice) can be applied to any scenario where:
- A user-initiated action has multiple valid paths
- The user should have visibility into the consequences of each path
- The default action should be the "safer" or more "expected" choice
- Examples: commit strategies, deployment targets, data import modes, migration options
