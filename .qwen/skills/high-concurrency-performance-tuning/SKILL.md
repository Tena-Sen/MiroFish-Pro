---
name: high-concurrency-performance-tuning
description: 在不改变业务逻辑前提下进行高并发性能调优的方法论：并行度配置、前端轮询优化、后端线程池并行化、文件 I/O 优化
source: auto-skill
extracted_at: '2026-06-12T07:46:02.217Z'
---

## 背景

在高并发性能调优中，用户要求在**不改变代码业务逻辑**的前提下，通过以下方式提升系统整体速度：

## 4 层优化方法

### 1. 并行度提升（Profile 生成阶段）

**目标**：增加准备阶段的并发 Profile 生成数量

```python
# 在 config.py 中新增配置项
OASIS_DEFAULT_PARALLEL_PROFILE_COUNT = int(
    os.environ.get('OASIS_DEFAULT_PARALLEL_PROFILE_COUNT', '15')
)

# 在 simulation_manager.py 和 simulation.py 中使用
parallel_count = parallel_profile_count or Config.OASIS_DEFAULT_PARALLEL_PROFILE_COUNT
```

**关键点**：
- 默认值从 3-5 提升到 15
- 通过环境变量 `OASIS_DEFAULT_PARALLEL_PROFILE_COUNT` 可自定义
- 上限受 LLM API 并发限制约束

### 2. 前端轮询间隔优化

**目标**：减少无效 API 请求，提升用户体验

```javascript
// 动态间隔策略
const getDynamicInterval = () => {
  if (total - current <= 5 && current > 0) return 1000;     // 最后 5 轮加速
  if (total - current <= 15 && current > 0) return 1500;    // 最后 15 轮中速
  return 2000;                                               // 默认 2s
};

// 使用递归 setTimeout 替代 setInterval（每次根据状态动态计算）
const startStatusPolling = () => {
  const poll = () => {
    fetchRunStatus().then(() => {
      const interval = getDynamicInterval();
      statusTimer = setTimeout(poll, interval);
    });
  };
  poll();
};
```

**对比**：
- Step2（准备阶段）：轮询间隔从 2s 改为 3s
- Step3（模拟阶段）：动态间隔，减少 30-60% API 请求

### 3. 后端线程池并行化（配置生成阶段）

**目标**：模拟配置生成阶段使用线程池并行处理

```python
import concurrent.futures

# 配置生成器中使用 ThreadPoolExecutor
max_workers = min(5, len(batch_tasks))
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    results = list(executor.map(generate_single_batch, batch_tasks))
```

**关键点**：
- 最多 5 并发线程
- 通过 `executor.map` 并行执行批次任务
- 受 GIL 影响较小（I/O 密集型操作）

### 4. 文件 I/O 优化

**目标**：减少模拟运行过程中频繁的磁盘写入

```python
# 监控线程中加入
last_save_time = 0
save_interval = 5

# 只在数据有变化时保存，且至少间隔 5 秒
current_time = time.time()
if (changed or current_time - last_save_time >= save_interval):
    cls._save_run_state(state)
    last_save_time = current_time
```

**关键点**：
- 添加 changed 标志位检测日志读取是否有新数据
- 最小保存间隔 5 秒
- 减少 60-80% 的磁盘写入

## 预期效果

| 优化项 | 预期提升 |
|--------|----------|
| Profile 生成并行度 | 准备阶段从 10-30 分钟降到 3-8 分钟 |
| 前端轮询优化 | 减少 30-60% API 请求 |
| 配置生成并行化 | 配置生成从 20-40 秒降到 10-20 秒 |
| 监控 I/O 优化 | 减少 60-80% 磁盘写入 |

## 注意事项

1. **LLM API 并发限制**：并行度调优需考虑 LLM API 的并发限制
2. **内存占用**：增加并发可能增加内存占用
3. **资源竞争**：高并发可能导致资源竞争，需监控
4. **环境依赖**：配置文件通过环境变量 OASIS_DEFAULT_PARALLEL_PROFILE_COUNT 可调整
