---
name: fix-simulation-snapshot-resume
description: Add --start-round support to MiroFish simulation scripts so snapshot restore can resume from the snapshot's round instead of always restarting from round 0
source: auto-skill
extracted_at: '2026-06-14T08:50:00.000Z'
---

## Problem
MiroFish's "restore snapshot" feature only copies files back (data rollback) but when the simulation restarts, it always starts from round 0 via a hardcoded `for round_num in range(total_rounds)` loop. This wastes time and breaks continuity — if you snapshot at round 500 and restore, you lose 500 rounds of work.

## Root Cause
The simulation script `run_parallel_simulation.py` (and its platform-specific variants) has a fixed forward iteration:
```python
for round_num in range(total_rounds):  # always starts at 0
```
There is no mechanism to read `current_round` from the restored `run_state.json` or accept a start-round argument.

## Scope of the Fix
Three files need changes:

### 1. `backend/app/services/simulation_runner.py`

**Snapshot creation** — record `current_round` in snapshot metadata:
```python
# In create_snapshot, after saving run_state.json:
run_state_path = os.path.join(snapshot_dir, "run_state.json")
if os.path.exists(run_state_path):
    with open(run_state_path, 'r', encoding='utf-8') as f:
        run_state = json.load(f)
    metadata["current_round"] = run_state.get("current_round", 0)
```

**Restore** — pass `--start-round` to the new simulation process:
```python
# In restore_snapshot or start_simulation, after restoring:
start_round = 0
metadata_path = os.path.join(snapshot_dir, "metadata.json")
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)
    start_round = metadata.get("current_round", 0)

# Build command with --start-round if not 0
cmd = [sys.executable, script_path, "--config", config_path]
if start_round > 0:
    cmd.extend(["--start-round", str(start_round)])
if max_rounds is not None and max_rounds > 0:
    cmd.extend(["--max-rounds", str(max_rounds)])
```

### 2. `backend/scripts/run_parallel_simulation.py`

**Accept `--start-round` argument:**
```python
parser.add_argument(
    '--start-round',
    type=int,
    default=0,
    help='Start simulation from this round number (for snapshot resume)'
)
```

**Modify the main loop:**
```python
# Before: for round_num in range(total_rounds):
start_round = args.start_round

# Adjust total_rounds if starting from a non-zero round
if start_round > 0 and args.max_rounds:
    effective_start = start_round
    effective_total = min(args.max_rounds, start_round + (args.max_rounds - start_round))
    total_rounds = max(start_round, effective_total)
elif start_round > 0:
    total_rounds = max(total_rounds, start_round)

for round_num in range(start_round, total_rounds):
```

**Adjust `initial_posts` handling:** If `start_round == 0`, run initial posts as before. If `start_round > 0`, skip initial posts since they've already been processed.

### 3. Platform-specific scripts (`run_twitter_simulation.py`, `run_reddit_simulation.py`)

Same `--start-round` argument and loop modification pattern as `run_parallel_simulation.py`.

## Verification Steps
1. Run a simulation, let it reach round 5-10
2. Take a snapshot
3. Stop the simulation
4. Restore the snapshot
5. Start again — verify logs show "Starting from round 5" or similar
6. Confirm the simulation continues from where it left off without re-running rounds 0-4

## Key Considerations
- **Agent graph state**: OASIS agents are created fresh each run. The database (`twitter_simulation.db`, `reddit_simulation.db`) is what preserves history. Since restore copies these DBs, agents starting from round N will see the same posts/interactions that existed at round N.
- **actions.jsonl**: Restoring this file means the log shows actions from 0 to snapshot round. If you skip initial posts when `start_round > 0`, the log remains consistent.
- **Graph memory updates**: The `GraphMemoryUpdater` sends world events to the knowledge graph in batches. When resuming, it should continue sending from where it left off (the restored `actions.jsonl` provides the history).
- **Snapshot metadata**: Adding `current_round` to `metadata.json` is non-breaking — existing snapshots without this field will default to round 0 (start from beginning).

## Why This Works Without Major Impact
- LLM decisions depend on the database (posts, comments, entity relationships), not on the `actions.jsonl` file
- The database is fully restored by the snapshot mechanism
- Skipping rounds 0-N in the loop just means the LLM API calls for those rounds don't happen again; the agents still see the same database state
- The only "loss" is that `simulation.log` and `actions.jsonl` won't have entries for the skipped rounds — purely a logging concern
