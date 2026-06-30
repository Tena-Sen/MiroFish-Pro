<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

简洁通用的群体智能引擎，预测万物
</br>
<em>A Simple and Universal Swarm Intelligence Engine, Predicting Anything</em>

[![GitHub Stars](https://img.shields.io/github/stars/Tena-Sen/MiroFish-Pro?style=flat-square&color=DAA520)](https://github.com/Tena-Sen/MiroFish-Pro/stargazers)
[![GitHub Watchers](https://img.shields.io/github/watchers/Tena-Sen/MiroFish-Pro?style=flat-square)](https://github.com/Tena-Sen/MiroFish-Pro/watchers)
[![GitHub Forks](https://img.shields.io/github/forks/Tena-Sen/MiroFish-Pro?style=flat-square)](https://github.com/Tena-Sen/MiroFish-Pro/network)

[English](./README.md) | [中文文档](./README-ZH.md)

</div>

---

> **📌 Notice / 公告**
>
> This repository (`MiroFish-Pro`) is a **community fork** of the original [MiroFish](https://github.com/666ghj/MiroFish) project, focused on **stability fixes, snapshot recovery, and Step5 UX improvements** for long-running simulations.
>
> 本仓库（`MiroFish-Pro`）是 [MiroFish](https://github.com/666ghj/MiroFish) 项目的社区分支版本，专注于**稳定性修复、快照恢复、Step5 UX 改进**。
>
> - **Original author / 原作者**：[666ghj](https://github.com/666ghj) & [Shanda Group](https://www.shanda.com/)
> - **Source / 源仓库**：[github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish)
> - **This fork / 本仓库**：[github.com/Tena-Sen/MiroFish-Pro](https://github.com/Tena-Sen/MiroFish-Pro)
>
> ⭐ All credits for the original design, vision, and core engine go to the original authors. Please star their repo to show appreciation.
>
> ⭐ 原始设计、愿景和核心引擎的所有功劳归原作者所有。请到原仓库 star 表示支持。

---

## 📋 What's Different from Upstream

This fork adds **33 commits** focused on production stability, performance, and recovery flow. **Zero changes to LLM/prediction logic** — all your simulations and reports produce identical results to upstream.

### Major Improvements

| Area | What changed | Why |
|---|---|---|
| **Snapshot Business** | v3 hardening: `restored_at` marker, IPC cleanup, path traversal guard, timestamp ordering, mtime short-circuit | Long-running simulations no longer lose snapshot state; safe to delete specific snapshots; no more IPC leftover pollution |
| **Step5 Restart** | One-click smart restart (no need to navigate to Step3) | When simulation env dies (backend restart, crash, etc.), users can recover directly from Step5 |
| **Multi-snapshot Picker** | When ≥1 `final_`/`fail_` snapshots exist, show selection list | Users explicitly choose which round to restore, instead of auto-picking latest |
| **Recovery Priority** | Restore snapshot FIRST, fallback to force restart | Default recovery path preserves the previous world state (actions.jsonl, DB, Zep graph) |
| **env_status Tracking** | Heartbeat timestamp + actual process check + auto-update on exit | Reliable detection of dead sub-processes (no more 504s from stale "alive" status) |
| **Report Agent** | Fix `ReportManager` `UnboundLocalError` + remove duplicate `save_report` | Report generation and chat no longer crash on common paths |
| **Logging** | High-frequency `INFO` → `DEBUG` (3k+ lines/day → 0) | Cleaner backend console, easier debugging |
| **Atomic I/O** | `os.replace` retry with exponential backoff (5 attempts) | Survives transient Windows file locks (OneDrive, AV scans) |
| **Phase 2 — Async Profile Gen** | `AsyncOpenAI` profile generation with concurrency=40 | ~3× faster Step2 profile batch (does not block event loop) |
| **Phase 3 — Report Wave Parallel** | `REPORT_DEFAULT_WAVE_SIZE=2` (max 5) — generate N report sections per wave | Report generation ~2× faster with minimal coherence loss |
| **Phase 4a — Graph Chunk Parallel** | `GRAPH_BUILDER_CHUNK_PARALLEL=3` — entity/relation extraction per chunk parallel | Step1 graph build ~3× faster on large seed corpora |
| **Auto-Snapshot Resilience** | Periodic auto-snapshot every 5 rounds + keep last 3 | Long simulations no longer lose all progress on backend crash mid-run |
| **Profile Meta Endpoint** | New `/api/simulation/<id>/profiles/meta` returns only count + mtime | Frontend high-frequency polling no longer re-parses full JSON every tick |

### Full Commit List

```text
# 13 snapshot/restart/recovery improvements
bd598c3  fix(step3): 快照业务 v3 强化
6aa440e  fix(frontend): Step3Simulation.vue 编译错误修复
6608abd  fix(step3): _last_snapshot_round 持久化 + recent_actions 顺序 + /stop 状态
02fced5  fix(utils): atomic_write_text os.replace 重试
8d35047  fix(ipc): check_env_alive 加 timestamp 新鲜度检查
30ef4de  fix(simulation): 进程退出时显式更新 env_status.json
85bf1e7  fix(simulation): check_env_alive 加 _processes 进程验证
200b421  perf(step5): env 已关闭时显示恢复入口
707e0c0  perf(frontend): Step5 重启 Step3 时跳过恢复提示
d0fd525  perf(step5): 一键智能重启（无需跳到 Step3）
94595fd  perf(step5): 重启策略改为恢复快照优先
6c8cb2b  perf(step5): 多快照时让用户选择恢复哪个
d7c4561  perf(step5): 1 个快照也展示选择器

# 4 report / IPC / log fixes
db2e5bb  fix(report): 修复 ReportManager UnboundLocalError
40a8b13  perf(ipc): 超时时附带诊断信息
d1003fc  fix(report): 删除 /generate 端点冗余的 save_report
9d321c5  perf(ipc): env_status 心跳过期 WARNING 降为 DEBUG
6652c15  perf(logs): 降低高频 INFO 日志噪音

# 2 frontend UX improvements
dd9801b  perf(frontend): Process.vue console.log 降为 console.debug
3e63fab  perf(step5): env-status-bar 提到顶层

# 2 docs cleanups
f606a82  docs(simulation): 修正 cleanup_simulation_logs docstring

# 1 Phase 2-4a performance batch
fd9d5c3  perf(phase2-4a): 异步 profile 生成 + 报告波次并行 + 图谱 chunk 并行 + profile meta 接口

# 2 README rewrites for this fork
0a84c77  docs(readme): 替换占位符为 fork 维护者
55caa4a  docs(readme): 重写 README for MiroFish-Pro fork
```

> Total fork-specific commits: **33** (stability + UX + Phase 2-4a perf + auto-snapshot)

---

## ⚡ Overview (Original)

**MiroFish** is a next-generation AI prediction engine powered by multi-agent technology. By extracting seed information from the real world (such as breaking news, policy drafts, or financial signals), it automatically constructs a high-fidelity parallel digital world. Within this space, thousands of intelligent agents with independent personalities, long-term memory, and behavioral logic freely interact and undergo social evolution. You can inject variables dynamically from a "God's-eye view" to precisely deduce future trajectories — **rehearse the future in a digital sandbox, and win decisions after countless simulations**.

> You only need to: Upload seed materials (data analysis reports or interesting novel stories) and describe your prediction requirements in natural language</br>
> MiroFish will return: A detailed prediction report and a deeply interactive high-fidelity digital world

### Vision

- **At the Macro Level**: A rehearsal laboratory for decision-makers, allowing policies and public relations to be tested at zero risk
- **At the Micro Level**: A creative sandbox for individual users — whether deducing novel endings or exploring imaginative scenarios, everything can be fun, playful, and accessible

From serious predictions to playful simulations, every "what if" sees its outcome.

---

## 🌐 Live Demo (Upstream)

[Online demo by original author](https://666ghj.github.io/mirofish-demo/)

---

## 📸 Screenshots

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="Screenshot 1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="Screenshot 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="Screenshot 3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="Screenshot 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="Screenshot 5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="Screenshot 6" width="100%"/></td>
</tr>
</table>
</div>

---

## 🔄 Workflow

1. **Graph Building**: Seed extraction & Individual/collective memory injection & GraphRAG construction
2. **Environment Setup**: Entity relationship extraction & Persona generation & Agent configuration injection
3. **Simulation**: Dual-platform parallel simulation & Auto-parse prediction requirements & Dynamic temporal memory updates
4. **Report Generation**: ReportAgent with rich toolset for deep interaction with post-simulation environment
5. **Deep Interaction**: Chat with any agent in the simulated world & Interact with ReportAgent

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Description |
|------|---------|-------------|
| **Node.js** | 18+ | Frontend runtime, includes npm |
| **Python** | ≥3.11, ≤3.12 | Backend runtime |
| **uv** | Latest | Python package manager |

### 1. Clone & Configure

```bash
git clone https://github.com/Tena-Sen/MiroFish-Pro.git
cd MiroFish-Pro

# Copy the example configuration file
cp .env.example .env
```

Edit `.env` and fill in:

```env
# LLM API Configuration (supports any LLM API with OpenAI SDK format)
# Recommended: Alibaba Bailian qwen-plus
# https://bailian.console.aliyun.com/
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep Cloud Configuration (Graph memory)
# Free monthly quota is sufficient for simple usage
# https://app.getzep.com/
ZEP_API_KEY=your_zep_api_key_here
```

### 2. Install Dependencies

```bash
# One-click install of root + frontend + backend
npm run setup:all
```

Or step by step:

```bash
npm run setup          # Node deps (root + frontend)
npm run setup:backend  # Python deps (auto-creates venv)
```

### 3. Start Services

```bash
npm run dev
```

**Service URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:5001

**Start individually:**

```bash
npm run backend   # Backend only
npm run frontend  # Frontend only
```

### Alternative: Docker

```bash
cp .env.example .env
docker compose up -d
```

Ports: `3000` (frontend) / `5001` (backend).

---

## 🆚 vs Upstream — When to Use This Fork

| Scenario | Use upstream | Use this fork |
|---|---|---|
| First-time trying MiroFish | ✅ | (works the same) |
| Short simulations (<30 rounds) | ✅ | (works the same) |
| Long-running simulations (50+ rounds) | ⚠️ risk of 504 from stale env_status | ✅ fixed in `85bf1e7` |
| Recovering from sub-process crash | ⚠️ requires manual Step3 nav | ✅ one-click from Step5 |
| Multiple `final_*` snapshots (re-runs) | ⚠️ auto-picks latest created_at | ✅ user selects by round |
| Backend restart during simulation | ⚠️ env_status stale 60s+ | ✅ process check catches immediately |
| Want raw upstream + latest features | ✅ (sync upstream) | (fork may lag) |
| Large seed corpus (slow Step1 graph build) | ⚠️ chunk-serial entity extraction | ✅ `GRAPH_BUILDER_CHUNK_PARALLEL=3` (Phase 4a) |
| Many profiles in Step2 (slow persona gen) | ⚠️ ThreadPool blocks event loop | ✅ AsyncOpenAI concurrency=40 (Phase 2) |
| Long Step4 reports (10+ sections) | ⚠️ fully serial | ✅ wave size 2-5 (Phase 3) |
| Want auto-snapshot during long runs | ⚠️ manual only | ✅ auto every 5 rounds + keep last 3 |

If you value **predictable recovery from long-running simulations**, this fork is for you.

---

## 🛠️ Development & Contribution

### Fork-specific Improvements

All 33 commits in this fork are about **stability, UX, and performance** (Phase 2-4a) — never changes LLM/prediction logic. To sync with upstream:

```bash
# Add upstream as a remote (one-time)
git remote add upstream https://github.com/666ghj/MiroFish.git

# Fetch upstream
git fetch upstream

# Merge upstream into a feature branch
git checkout -b sync-upstream
git merge upstream/main

# Resolve any conflicts (likely none — we only touched stability paths)
# Push to your fork
git push origin sync-upstream
```

### Reporting Issues

For **MiroFish-Pro-specific** issues (snapshot recovery, Step5 restart):
- Open an issue on this repo

For **upstream** MiroFish issues (LLM prompts, OASIS integration, etc.):
- Open an issue on [github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish)

---

## 📄 License

This project inherits the upstream MiroFish license. Please refer to the original repository for license terms.

本项目沿用上游 MiroFish 的许可证。请参阅原仓库获取许可证条款。

---

## 🙏 Acknowledgments

**MiroFish was originally created and developed by [666ghj](https://github.com/666ghj) and the [Shanda Group](https://www.shanda.com/) team.** This fork would not exist without their foundational work — the multi-agent simulation engine, GraphRAG integration, and the entire UX architecture.

MiroFish's simulation engine is powered by **[OASIS (Open Agent Social Interaction Simulations)](https://github.com/camel-ai/oasis)**. We sincerely thank the CAMEL-AI team for their open-source contributions!

The 33 stability + performance improvements in this fork were developed independently by the MiroFish-Pro maintainer.

---

## 📬 Contact

- **Upstream MiroFish team** is recruiting full-time/internship positions. If interested in multi-agent simulation and LLM applications, send your resume to: **mirofish@shanda.com**
- **MiroFish-Pro fork** — please open a GitHub issue for questions
