---
name: fix-delete-persistence-bug
description: Fix incomplete deletion where files are removed but empty directories persist, or stale file handles cause 404-after-delete
source: auto-skill
extracted_at: '2026-06-12T01:40:00.000Z'
---

# Fix Incomplete Deletion — Files Removed But Directories Persist

When a delete API reports success but the filesystem still shows residual files or empty directories, the bug is almost always caused by one of two patterns:

## Root Causes

### Cause 1: Path Construction Method Creates Empty Directories

Methods like `_get_simulation_dir()` that use `os.makedirs(path, exist_ok=True)` will **create** the directory even if you only intend to read from it. When the delete flow calls this method to get the path, the empty directory is created before the deletion even starts.

```python
# BAD — creates empty dir on read
sim_dir = manager._get_simulation_dir(simulation_id)

# GOOD — direct path construction, no side effects
sim_dir = os.path.join(manager.SIMULATION_DATA_DIR, simulation_id)
```

### Cause 2: Redundant File Deletion After Directory Already Removed

```python
# BUG: shutil.rmtree already deleted the directory
shutil.rmtree(sim_dir)

# This code NEVER executes because sim_dir no longer exists
run_state_file = os.path.join(sim_dir, "run_state.json")
if os.path.exists(run_state_file):
    os.remove(run_state_file)
```

### Cause 3: No Cleanup of Empty Directories After `shutil.rmtree`

`shutil.rmtree()` deletes all files inside but may leave empty parent directories if they were created separately or by concurrent operations.

## Fix Procedure

### Step 1: Identify the Deletion Flow

Trace the delete API from route handler to filesystem operations. Document every directory/file it touches.

### Step 2: Eliminate Side-Effect Path Construction

Replace any call to path-construction methods that use `os.makedirs` with direct path concatenation:

```python
# Before
sim_dir = manager._get_simulation_dir(simulation_id)

# After
sim_dir = os.path.join(manager.SIMULATION_DATA_DIR, simulation_id)
```

### Step 3: Remove Redundant Deletion Code

If `shutil.rmtree(sim_dir)` already handles everything, remove any subsequent file-level `os.remove()` calls on paths within that directory.

### Step 4: Add Empty Directory Cleanup

After the main deletion, attempt to clean up any empty directory that might remain:

```python
shutil.rmtree(sim_dir)
logger.info(f"已删除模拟数据目录: {sim_dir}")

# Clean up potentially remaining empty directory
if os.path.exists(sim_dir):
    try:
        os.rmdir(sim_dir)
        logger.info(f"已清理空目录: {sim_dir}")
    except OSError:
        pass  # Directory is not empty or cannot be removed — ignore
```

### Step 5: Verify Deletion Is Complete

1. **API verification**: Call the get/list API for the deleted entity — should return 404 or not appear in list
2. **Filesystem verification**: Check that the directory and all files are gone
3. **Frontend verification**: Entity is removed from the UI list

## Verification Script

```bash
# Before delete: show files
dir /s /b backend\uploads\simulations\sim_xxxxx

# Call DELETE API
curl -X DELETE http://127.0.0.1:5001/api/simulation/sim_xxxxx

# After delete: should return empty
dir /s /b backend\uploads\simulations\sim_xxxxx

# API should return 404
curl http://127.0.0.1:5001/api/simulation/sim_xxxxx
# Expected: {"success": false, "error": "模拟不存在: sim_xxxxx"}
```

## Key Takeaway

> **Never use path-construction methods that create directories on the filesystem if you only need the path string.** Always construct paths directly when the directory might be about to be deleted. After `shutil.rmtree()`, always attempt to clean up the empty parent directory with `os.rmdir()`.
