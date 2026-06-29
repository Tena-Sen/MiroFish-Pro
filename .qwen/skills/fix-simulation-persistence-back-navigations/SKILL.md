---
name: fix-simulation-persistence-back-navigations
description: Fix losing all simulation results when navigating back from Step 3 (simulation run) or Step 4 (report generation) by implementing automatic final snapshots and preserving simulation environment state on navigation
source: auto-skill
extracted_at: '2026-06-14T03:54:56.081Z'
---

# Fix Simulation State Lost on Back Navigation

When a user completes a simulation in Step 3, proceeds to Step 4 (report), then navigates back to Step 3, the simulation state is completely lost — the user sees a fresh empty state instead of the previous simulation's final results. This happens because:

1. No automatic snapshot is created when the simulation **succeeds** (only on failure)
2. Navigation back from Step 3 closes the simulation environment and kills the process
3. Re-entering Step 3 always starts a fresh simulation with `force: true`

## Symptom

- User completes simulation (all platforms reach final round)
- User generates report (Step 4) and reviews it
- User clicks "Back to Step 3" — sees empty state, no simulation data
- Starting simulation again restarts from scratch with `force: true`
- Only snapshot feature exists for **failed** simulations, not successful ones

## Root Cause Analysis

### Problem 1: No Final Snapshot on Success

```javascript
// In Step3Simulation.vue, fetchRunStatus()

if (data.runner_status === 'failed') {
  // Only this path creates a snapshot
  await autoCreateSnapshotOnFail(data)
} else {
  // Success path — no snapshot!
  emit('update-status', 'completed')
}
```

The simulation saves **nothing** when it completes successfully. When the environment is later closed, all runtime data (actions, agent profiles, databases) is lost forever.

### Problem 2: Navigation Back Closes the Environment

```javascript
// In SimulationRunView.vue handleGoBack()

// BEFORE FIX:
if (envStatusRes.data?.env_alive) {
  await closeSimulationEnv({ simulation_id })  // Kills the simulation
}
if (isSimulating) {
  await stopSimulation({ simulation_id })      // Kills the process
}
router.push({ name: 'Simulation', params })    // User loses everything
```

### Problem 3: Re-entry Always Forces New Simulation

```javascript
// In Step3Simulation.vue doStartSimulation()

resetAllState()  // Clears all state
startSimulation({ force: true })  // Forces restart from scratch
```

## Fix Procedure

### Step 1: Auto-Create Final Snapshot on Success

In `Step3Simulation.vue`, add a snapshot creation call for successful completion:

```javascript
// In fetchRunStatus(), after detecting completion:

if (data.runner_status === 'failed') {
  addLog(t('log.simFailed', { error: data.error || 'Unknown error' }))
  emit('update-status', 'failed')
  await autoCreateSnapshotOnFail(data)
} else {
  addLog(t('log.simCompleted'))
  emit('update-status', 'completed')
  // ✅ ADD: auto-create final snapshot on success
  await autoCreateSnapshotOnComplete(data)
}

// Add the new method:
const autoCreateSnapshotOnComplete = async (completeData) => {
  if (!props.simulationId) return
  const totalRound = completeData.total_rounds || '?'
  const name = `final_R${totalRound}`

  addLog(t('log.autoFinalSnapshotCreating', { round: totalRound }))

  try {
    const res = await createSnapshot(props.simulationId, { snapshot_name: name })
    if (res.success) {
      addLog(t('log.autoFinalSnapshotCreated', { name: res.data.snapshot_name }))
    } else {
      addLog(t('log.autoSnapshotFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.autoSnapshotException', { error: err.message }))
  }
}
```

### Step 2: Stop Closing Environment on Navigation Back

In `SimulationRunView.vue`, simplify `handleGoBack` to just stop polling and navigate:

```javascript
const handleGoBack = async () => {
  // ✅ NO LONGER close simulation env or stop process
  // Snapshots already saved the final state
  addLog(t('log.preparingGoBack'))
  stopGraphRefresh()
  router.push({ name: 'Simulation', params: { simulationId: currentSimulationId.value } })
}
```

Also update `SimulationView.vue`:
- Remove `checkAndStopRunningSimulation()` call from `onMounted`
- Remove `checkAndStopRunningSimulation` and `forceStopSimulation` methods
- Clean up unused imports (`stopSimulation`, `closeSimulationEnv`, `getEnvStatus`)

### Step 3: Add i18n Entries

```json
// zh.json
"log.autoFinalSnapshotCreating": "自动创建最终快照：R{round}",
"log.autoFinalSnapshotCreated": "✓ 最终快照已创建：{name}"

// en.json
"log.autoFinalSnapshotCreating": "Auto-creating final snapshot: R{round}",
"log.autoFinalSnapshotCreated": "✓ Final snapshot created: {name}"
```

### Step 4: Verify the Flow

```
Step 3 simulation completes → final_R{n} snapshot auto-created
→ Step 4 (report) → click "Back to Step 3"
→ SimulationRunView loads → no env close → simulationId loaded
→ User can see snapshots in snapshot panel
→ User can restore from snapshot or start new simulation (force: true)
```

## Architecture Notes

The snapshot system already existed and was well-implemented:

- **Backend**: `SimulationRunner.create_snapshot()` saves `run_state.json`, `simulation_config.json`, `actions.jsonl`, `profiles.json`, and database files to `RUN_STATE_DIR/simulation_id/snapshots/snapshot_name/`
- **Backend**: `restore_snapshot()` copies files back from snapshot to simulation directory
- **Frontend**: `createSnapshot()`, `restoreSnapshot()`, `listSnapshots()` all exist in `simulation.js` API
- **Frontend**: Snapshot panel exists in Step 3 UI

The fix is purely about **when** to create the final snapshot and **not destroying** the environment on navigation.

## Alternative: Auto-Restore on Entry

An even more seamless approach would be to auto-restore the latest snapshot when entering Step 3 if one exists:

```javascript
// In SimulationRunView.vue onMounted:

const loadSimulationData = async () => {
  // ... existing code ...

  // Check if a snapshot exists and auto-restore
  try {
    const snapRes = await listSnapshots(currentSimulationId.value)
    if (snapRes.success && snapRes.data?.snapshots?.length > 0) {
      const latest = snapRes.data.snapshots[0]
      addLog(t('log.foundLastSnapshot', { name: latest.name }))
      // User confirms before auto-restore
      const restoreRes = await restoreSnapshot(currentSimulationId.value, { snapshot_name: latest.name })
      if (restoreRes.success) {
        addLog(t('log.autoRestoredFromSnapshot', { name: latest.name }))
      }
    }
  } catch (err) {
    // No snapshots, proceed with fresh state
  }
}
```

This is more aggressive but provides the "pick up where you left off" experience without manual steps.

## Key Takeaway

> **Don't destroy state when the user navigates back — just save it.** The snapshot system was already there as a safety net for failures. Extending it to also cover the success path eliminates the destructive "close environment on back navigation" pattern. Navigation back should be lossless.
