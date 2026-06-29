---
name: fix-state-sync-bug
description: Diagnose and fix state sync issues between parallel state stores (e.g., Runner vs Manager) causing phantom running states
source: auto-skill
extracted_at: '2026-06-11T16:21:39.773Z'
---

# Fix State Sync Bug Between Parallel State Stores

When a process or simulation crashes/fails but the frontend still shows it as "running", there is likely a state sync gap between parallel state stores.

## Pattern

The architecture has two (or more) state stores that describe the same entity:
- **Manager state** (e.g., `state.json` via SimulationManager) — the "source of truth" for the UI
- **Runner state** (e.g., `run_state.json` via SimulationRunner) — updated by the long-running process

When the runner process exits (success, failure, or manual stop), only the runner state is updated. The manager state is never notified, so the frontend polls a stale `"running"` status forever.

## Diagnosis Procedure

1. **Confirm the symptom**: Frontend keeps polling despite the process being dead
2. **Find the two state stores**: Search for files like `*.json` or ORM models that track the same entity
3. **Trace the failure path**: When the process crashes, which code updates which state file?
4. **Verify the gap**: On failure, does the manager state get updated? If not — that's the bug.

## Fix Pattern

Add a sync method in the runner that maps its status to the manager's status enum and saves:

```python
@classmethod
def _sync_manager_state(cls, simulation_id: str, run_state: SimulationRunState):
    """Sync runner status back to manager state.json on process end."""
    try:
        from .simulation_manager import SimulationManager, SimulationStatus
        manager = SimulationManager()
        sim_state = manager.get_simulation(simulation_id)
        if not sim_state:
            return
        status_map = {
            RunnerStatus.COMPLETED: SimulationStatus.COMPLETED,
            RunnerStatus.FAILED: SimulationStatus.FAILED,
            RunnerStatus.STOPPED: SimulationStatus.STOPPED,
        }
        new_status = status_map.get(run_state.runner_status)
        if new_status:
            sim_state.status = new_status
            sim_state.current_round = run_state.current_round
            sim_state.error = run_state.error
            manager._save_simulation_state(sim_state)
    except Exception as e:
        logger.error(f"Sync failed: {simulation_id}, error={e}")
```

**Call this method at every exit path** in the monitor loop:
- After `completed` (normal end)
- After `failed` (crash or error)
- After `stopped` (manual stop)

## Frontend Defense

Even with the backend fix, the frontend should also stop polling when it sees a failure status:

```javascript
const isCompleted = data.runner_status === 'completed' || 
                    data.runner_status === 'stopped' || 
                    data.runner_status === 'failed'

if (isCompleted) {
  if (data.runner_status === 'failed') {
    addLog(t('log.simFailed', { error: data.error || 'Unknown' }))
    emit('update-status', 'failed')
  }
  stopPolling()
}
```

Also guard `startPolling()` with an early return when already complete:

```javascript
const startPolling = () => {
  if (agentLogTimer || consoleLogTimer) return
  if (isComplete.value) return  // Prevent double-start
  fetchAgentLog()
  fetchConsoleLog()
  agentLogTimer = setInterval(fetchAgentLog, 2000)
  consoleLogTimer = setInterval(fetchConsoleLog, 1500)
}
```

## Key Takeaway

> **Always sync state back to the UI-facing store on every terminal state**, not just on success. The manager state is what the frontend polls — it must reflect the true state of the world.
