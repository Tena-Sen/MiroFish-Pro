"""
OASIS模拟运行器
在后台运行模拟并记录每个Agent的动作，支持实时状态监控
"""

import os
import sys
import json
import time
import asyncio
import threading
import subprocess
import signal
import atexit
from collections import deque
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale
from ..utils.atomic_io import atomic_write_json
from .zep_graph_memory_updater import ZepGraphMemoryManager
from .simulation_ipc import SimulationIPCClient, CommandType, IPCResponse

logger = get_logger('mirofish.simulation_runner')

# 标记是否已注册清理函数
_cleanup_registered = False

# 平台检测
IS_WINDOWS = sys.platform == 'win32'


class RunnerStatus(str, Enum):
    """运行器状态"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent动作记录"""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """每轮摘要"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """模拟运行状态（实时）"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE

    # 进度信息
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0

    # 用户传入的目标最大轮数（用于截断），0 表示未设置
    # 快照必须显式记录此值，以便恢复时知道原始意图
    user_max_rounds: int = 0
    
    # 各平台独立轮次和模拟时间（用于双平台并行显示）
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    
    # 平台状态
    twitter_running: bool = False
    reddit_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    
    # 平台完成状态（通过检测 actions.jsonl 中的 simulation_end 事件）
    twitter_completed: bool = False
    reddit_completed: bool = False

    # 周期性自动快照追踪：上次触发快照的轮次
    # 修复（NameError）：之前 last_snapshot_round 是 _monitor_simulation 的闭包变量，
    # 被 @classmethod _read_action_log 引用，Python 抛 UnboundLocalError。
    # 修复：移到 state 对象上，跨方法可见、且能被 to_dict 序列化到 run_state.json
    # 业务语义不变：-1 = 尚未快照过；>=0 = 上一轮触发了快照
    _last_snapshot_round: int = -1

    # actions.jsonl 读取位置（防止快照恢复时重读旧 actions）
    # 修复（快照恢复重复读取 R0~R4 的 bug）：
    # 之前 _monitor_simulation 每次启动 twitter_position/reddit_position 都重置为 0，
    # 导致 restore_snapshot 后 monitor 从头读旧 actions.jsonl，把 R0~R4 重复加进 recent_actions。
    # 修复：持久化到 state（run_state.json），monitor 启动时恢复位置继续读。
    twitter_actions_log_position: int = 0
    reddit_actions_log_position: int = 0

    # 每轮摘要
    rounds: List[RoundSummary] = field(default_factory=list)

    # 最近动作（用于前端实时展示）
    # 优化 B6：用 deque(maxlen=50) 替代 list，appendleft + 自动截断 O(1)
    # 业务语义不变：仍按"最新在前"顺序，max 50 条
    # 注意：maxlen 直接在 deque 构造里硬编码 50；旧版本独立字段 max_recent_actions
    # 已被移除（无任何代码读取，纯死字段）
    recent_actions: "deque" = field(default_factory=lambda: deque(maxlen=50))

    # 优化 B2：脏标记 —— state 字段被改动后置 True，由 _save_run_state_if_dirty 统一落盘
    # 业务语义不变：磁盘最终内容与原版完全一致
    _dirty: bool = False

    # 时间戳
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    # 错误信息
    error: Optional[str] = None

    # 进程ID（用于停止）
    process_pid: Optional[int] = None

    def add_action(self, action: AgentAction):
        """添加动作到最近动作列表"""
        # 优化 B6：deque.appendleft + 自动截断（O(1)）
        self.recent_actions.appendleft(action)

        if action.platform == "twitter":
            self.twitter_actions_count += 1
        else:
            self.reddit_actions_count += 1

        self.updated_at = datetime.now().isoformat()
        self._dirty = True  # 优化 B2：标脏

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # 用户原始的 max_rounds（用于快照诊断/恢复）
            "user_max_rounds": self.user_max_rounds,
            # 各平台独立轮次和时间
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count,
            # 必修 1：持久化 _last_snapshot_round（避免重启后立刻又触发一次 auto-snapshot）
            "_last_snapshot_round": self._last_snapshot_round,
            # 修复（快照恢复重复读旧 actions bug）：
            # actions.jsonl 读取位置必须持久化到 run_state.json，
            # 否则 monitor 重启时仍会从 0 重读快照里的旧 actions。
            "twitter_actions_log_position": self.twitter_actions_log_position,
            "reddit_actions_log_position": self.reddit_actions_log_position,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }

    def to_detail_dict(self) -> Dict[str, Any]:
        """包含最近动作的详细信息"""
        result = self.to_dict()
        # deque 同样支持迭代 + list(...) 转 list，下游 [a.to_dict() for a in ...] 不变
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result


class SimulationRunner:
    """
    模拟运行器
    
    负责：
    1. 在后台进程中运行OASIS模拟
    2. 解析运行日志，记录每个Agent的动作
    3. 提供实时状态查询接口
    4. 支持暂停/停止/恢复操作
    """
    
    # 运行状态存储目录
    RUN_STATE_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )
    
    # 脚本目录
    SCRIPTS_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../scripts'
    )
    
    # 内存中的运行状态
    _run_states: Dict[str, SimulationRunState] = {}
    _processes: Dict[str, subprocess.Popen] = {}
    _action_queues: Dict[str, Queue] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _stdout_files: Dict[str, Any] = {}  # 存储 stdout 文件句柄
    _stderr_files: Dict[str, Any] = {}  # 存储 stderr 文件句柄
    
    # 图谱记忆更新配置
    _graph_memory_enabled: Dict[str, bool] = {}  # simulation_id -> enabled

    @classmethod
    def get_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """获取运行状态"""
        if simulation_id in cls._run_states:
            return cls._run_states[simulation_id]
        
        # 尝试从文件加载
        state = cls._load_run_state(simulation_id)
        if state:
            cls._run_states[simulation_id] = state
        return state
    
    @classmethod
    def _load_run_state(cls, simulation_id: str) -> Optional[SimulationRunState]:
        """从文件加载运行状态"""
        state_file = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            state = SimulationRunState(
                simulation_id=simulation_id,
                runner_status=RunnerStatus(data.get("runner_status", "idle")),
                current_round=data.get("current_round", 0),
                total_rounds=data.get("total_rounds", 0),
                simulated_hours=data.get("simulated_hours", 0),
                total_simulation_hours=data.get("total_simulation_hours", 0),
                # 旧快照可能没有这个字段，data.get 默认 0
                user_max_rounds=data.get("user_max_rounds", 0),
                # 各平台独立轮次和时间
                twitter_current_round=data.get("twitter_current_round", 0),
                reddit_current_round=data.get("reddit_current_round", 0),
                twitter_simulated_hours=data.get("twitter_simulated_hours", 0),
                reddit_simulated_hours=data.get("reddit_simulated_hours", 0),
                twitter_running=data.get("twitter_running", False),
                reddit_running=data.get("reddit_running", False),
                twitter_completed=data.get("twitter_completed", False),
                reddit_completed=data.get("reddit_completed", False),
                twitter_actions_count=data.get("twitter_actions_count", 0),
                reddit_actions_count=data.get("reddit_actions_count", 0),
                started_at=data.get("started_at"),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                completed_at=data.get("completed_at"),
                error=data.get("error"),
                process_pid=data.get("process_pid"),
            )
            
            # 加载最近动作（JSON 按 [新→旧] 顺序存，deque 也需保持此顺序）
            # 修复（必修 14）：用 append（不是 appendleft）保持磁盘顺序
            # 旧实现用 appendleft 反而把方向反了 — 加载后 deque 左端是最旧而非最新，
            # 后续 add_action 又往左 append，会导致"左端是最新还是最旧"取决于是否经历过 load，
            # 跨重启时 recent_actions 顺序完全错乱
            # 业务语义：磁盘 [新, 第二新, ..., 最旧] → deque [新, 第二新, ..., 最旧]（左端最新）
            actions_data = data.get("recent_actions", [])
            for a in actions_data:
                state.recent_actions.append(AgentAction(
                    round_num=a.get("round_num", 0),
                    timestamp=a.get("timestamp", ""),
                    platform=a.get("platform", ""),
                    agent_id=a.get("agent_id", 0),
                    agent_name=a.get("agent_name", ""),
                    action_type=a.get("action_type", ""),
                    action_args=a.get("action_args", {}),
                    result=a.get("result"),
                    success=a.get("success", True),
                ))

            # 必修 1：恢复 _last_snapshot_round
            # 旧实现不持久化 → 重启后总是 -1 → 周期性自动快照会立刻重跑一次（浪费磁盘）
            # 用 max() 兜底：即使 JSON 中值是 -1 也接受（边界情况，意思相同）
            if hasattr(state, "_last_snapshot_round"):
                state._last_snapshot_round = int(data.get("_last_snapshot_round", -1))

            # 修复（快照恢复重复读旧 actions bug）：
            # 恢复 actions.jsonl 读取位置；缺省视为 0（向后兼容老 run_state）
            state.twitter_actions_log_position = int(data.get("twitter_actions_log_position", 0))
            state.reddit_actions_log_position = int(data.get("reddit_actions_log_position", 0))

            return state
        except Exception as e:
            logger.error(f"加载运行状态失败: {str(e)}")
            return None
    
    @classmethod
    def _save_run_state(cls, state: SimulationRunState, force: bool = False):
        """保存运行状态到文件

        Args:
            state: 运行状态对象
            force: 是否强制写入（默认 False，标脏时由调用方决定）

        业务语义不变：磁盘最终内容与原版完全一致。
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        state_file = os.path.join(sim_dir, "run_state.json")

        data = state.to_detail_dict()

        # 使用原子写入：监控线程每 5s 写一次，前端每 2-3s 读取，避免读到半截 JSON
        atomic_write_json(state_file, data)

        # 写盘完成后清脏标记
        state._dirty = False
        cls._run_states[state.simulation_id] = state

    @classmethod
    def _cleanup_ipc_dirs(cls, simulation_id: str) -> None:
        """
        关键修复（BUG-7/8）：清理 ipc_commands/ 和 ipc_responses/ 残留。
        旧实现不删这两个目录，force=true 重启 / restore_snapshot 后，
        新子进程 IPC server poll_commands 读到旧命令，server 端用相同 command_id 发响应，
        新 Flask 端 IPC client 等不到（它等的是新 command_id），旧响应残留
        解决：清空两个目录内所有 .json，与 IPC client/server 协议一致。
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        for ipc_dir_name in ("ipc_commands", "ipc_responses"):
            ipc_dir_path = os.path.join(sim_dir, ipc_dir_name)
            if not os.path.isdir(ipc_dir_path):
                continue
            try:
                for entry in os.listdir(ipc_dir_path):
                    if not entry.endswith(".json"):
                        continue
                    try:
                        os.remove(os.path.join(ipc_dir_path, entry))
                    except Exception as e:
                        logger.warning(f"清理 IPC {ipc_dir_name}/{entry} 失败: {e}")
                logger.info(f"已清理 IPC 目录残留: {ipc_dir_name}/")
            except Exception as e:
                logger.warning(f"清理 IPC 目录失败 {ipc_dir_name}: {e}")

    @classmethod
    def _cleanup_stale_simulation_resources(cls, simulation_id: str, reason: str = "") -> None:
        """
        清理某个 simulation_id 残留的子进程、监控线程和共享资源。

        用于：
        1. _start_simulation_impl 启动新进程前（防止双进程并发）
        2. restore_snapshot 后清理旧资源（可选，作为 _start_simulation_impl 的预清理）

        清理范围：
        - cls._processes[simulation_id]          # 旧的子进程（终止+清理引用）
        - cls._monitor_threads[simulation_id]     # 旧的监控线程（join+清理引用）
        - cls._action_queues[simulation_id]       # 旧的动作队列
        - cls._graph_memory_enabled[simulation_id] # 旧的图谱更新器标志
        - cls._stdout_files[simulation_id]        # 旧的 stdout 文件句柄
        - cls._stderr_files[simulation_id]        # 旧的 stderr 文件句柄

        Args:
            simulation_id: 模拟 ID
            reason: 清理原因（仅用于日志）
        """
        log_prefix = f"[清理残留资源] {simulation_id}"
        if reason:
            log_prefix += f" ({reason})"
        logger.info(log_prefix)

        # 1. 终止旧进程
        old_process = cls._processes.get(simulation_id)
        if old_process is not None:
            if old_process.poll() is None:
                logger.info(f"  - 终止旧子进程 PID={old_process.pid}")
                try:
                    cls._terminate_process(old_process, simulation_id, timeout=5)
                except Exception as e:
                    logger.warning(f"  - 终止旧子进程失败: {e}")
            else:
                logger.info(f"  - 旧子进程已退出（returncode={old_process.returncode}），跳过终止")
            cls._processes.pop(simulation_id, None)

        # 2. 等待旧监控线程退出
        # 监控线程会在其 finally 块中清理 stdout_files / stderr_files / _processes 等资源
        # 必须等它退出，否则它的 finally 块会清理掉我们即将创建的新资源
        old_monitor = cls._monitor_threads.get(simulation_id)
        if old_monitor is not None:
            if old_monitor.is_alive():
                logger.info("  - 等待旧监控线程退出（最多 10 秒）")
                old_monitor.join(timeout=10)
                if old_monitor.is_alive():
                    logger.warning("  - 旧监控线程 10 秒内未退出（可能仍持有 stdout 句柄）")
            cls._monitor_threads.pop(simulation_id, None)

        # 3. 清理其他共享资源（监控线程 finally 已清理一部分，这里是双保险）
        for dict_name in ("_action_queues", "_graph_memory_enabled"):
            target = getattr(cls, dict_name, None)
            if target is not None and simulation_id in target:
                target.pop(simulation_id, None)

        # 4. 关闭 stdout/stderr 文件句柄（如果监控线程还没来得及关）
        for files_dict_name in ("_stdout_files", "_stderr_files"):
            files_dict = getattr(cls, files_dict_name, None)
            if files_dict is None:
                continue
            fh = files_dict.get(simulation_id)
            if fh is not None:
                try:
                    fh.close()
                except Exception as e:
                    logger.warning(f"  - 关闭 {files_dict_name} 失败: {e}")
                files_dict.pop(simulation_id, None)

        # 5. 关键修复（BUG-7/8）：清理 IPC 命令/响应残留
        # 在启动新进程前清掉旧 IPC 命令，避免新子进程 IPC server 读到旧命令
        cls._cleanup_ipc_dirs(simulation_id)

        # 6. 必修 8：同时更新 env_status.json 到 stopped
        # 旧实现：清理旧资源时 env_status.json 保留 stale 'alive' 状态
        # 导致启动新进程前 check_env_alive 误判（必修 7 时间戳兜底 60s 延迟）
        # 这里直接更新到 stopped，让 check_env_alive 立即识别
        try:
            sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
            from .simulation_ipc import SimulationIPCClient
            ipc_client = SimulationIPCClient(sim_dir)
            ipc_client._update_env_status("stopped")
        except Exception:
            pass  # 兜底，不影响 cleanup 主流程

    @classmethod
    def _sync_manager_state(cls, simulation_id: str, run_state: SimulationRunState):
        """
        将 SimulationRunner 的运行状态同步回 SimulationManager 的 state.json。
        解决模拟进程结束/失败后 state.json 仍显示 running 的问题。
        """
        try:
            from .simulation_manager import SimulationManager, SimulationStatus

            manager = SimulationManager()
            sim_state = manager.get_simulation(simulation_id)
            if not sim_state:
                return

            # 根据 runner_status 映射到 SimulationStatus
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
                logger.info(f"已同步 state.json: {simulation_id} -> {new_status.value}")
        except Exception as e:
            logger.error(f"同步 state.json 失败: {simulation_id}, error={e}")

    @classmethod
    def start_simulation(
        cls,
        simulation_id: str,
        platform: str = "parallel",  # twitter / reddit / parallel
        max_rounds: int = None,  # 最大模拟轮数（可选，用于截断过长的模拟）
        enable_graph_memory_update: bool = False,  # 是否将活动更新到Zep图谱
        graph_id: str = None,  # Zep图谱ID（启用图谱更新时必需）
        start_round: int = 0,  # 从指定轮次开始（用于快照恢复后继续）
        chat_only: bool = False,  # 仅 chat 模式:跳过 rounds,直接进 IPC wait,agent 加载照常
    ) -> SimulationRunState:
        """
        启动模拟

        Args:
            simulation_id: 模拟ID
            platform: 运行平台 (twitter/reddit/parallel)
            max_rounds: 最大模拟轮数（可选，用于截断过长的模拟）
            enable_graph_memory_update: 是否将Agent活动动态更新到Zep图谱
            graph_id: Zep图谱ID（启用图谱更新时必需）
            start_round: 从指定轮次开始（0=从头开始）
            chat_only: 仅 chat 模式（True 时忽略 rounds,起子进程后直接进 IPC wait）

        Returns:
            SimulationRunState
        """
        try:
            return cls._start_simulation_impl(
                simulation_id, platform, max_rounds, enable_graph_memory_update, graph_id, start_round, chat_only
            )
        except (ValueError, KeyError):
            raise
        except Exception as e:
            logger.error(f"start_simulation 内部异常: simulation_id={simulation_id}, error={e}")
            raise ValueError(f"启动模拟内部错误: {str(e)}")

    @classmethod
    def _start_simulation_impl(
        cls,
        simulation_id: str,
        platform: str,
        max_rounds,
        enable_graph_memory_update: bool,
        graph_id: str,
        start_round: int,
        chat_only: bool = False,
    ) -> SimulationRunState:
        logger.info(f"_start_simulation_impl 开始: simulation_id={simulation_id}, platform={platform}, start_round={start_round}, max_rounds={max_rounds}, chat_only={chat_only}")

        # 加载模拟配置
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        if not os.path.exists(config_path):
            logger.error(f"模拟配置不存在: {config_path}")
            raise ValueError(f"模拟配置不存在，请先调用 /prepare 接口")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 初始化运行状态
        time_config = config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = int(total_hours * 60 / minutes_per_round)

        # chat-only 模式:把 start_round 提到 total_rounds,让下游 for 循环空跑直接进 IPC wait。
        # 只在用户没显式给 start_round 的情况下覆盖(避免跟快照恢复冲突)。
        if chat_only and start_round <= 0:
            start_round = total_rounds
            logger.info(
                f"chat-only 模式：effective_start_round = total_rounds = {start_round},"
                f"子进程 rounds loop 将空跑,直接进入 IPC wait"
            )

        # 记录起始轮次
        actual_start_round = 0
        if start_round > 0:
            actual_start_round = start_round
            logger.info(f"从轮次 {actual_start_round} 开始（已跳过 {start_round} 轮）")
        else:
            logger.info(f"将从头开始（start_round={start_round}）")

        # 快照恢复场景：尝试从 run_state.json 恢复 total_rounds / user_max_rounds
        # 无论选择"继续"还是"从头开始"，都应该恢复这些字段
        # 因为它们代表的是「整个模拟应有的总轮数/最大轮数」，不是剩余轮数
        # 重要：通过 run_state.json 中的 restored_at 标记判断是否刚被 restore_snapshot 重置过
        # （restore_snapshot 会写入 restored_at；普通启动没有这个字段）
        # 这样可以同时覆盖 start_round=0（start_over 模式）的快照恢复场景
        # 旧实现仅依赖 runner_status == 'idle'，在崩溃/异常路径下不可靠
        run_state_file = os.path.join(sim_dir, "run_state.json")
        restored_from_snapshot = False
        if os.path.exists(run_state_file):
            try:
                with open(run_state_file, 'r', encoding='utf-8') as f:
                    saved_state = json.load(f)
                saved_total_rounds = saved_state.get('total_rounds')
                saved_user_max_rounds = saved_state.get('user_max_rounds', 0)
                saved_runner_status = saved_state.get('runner_status', '')
                saved_restored_at = saved_state.get('restored_at', '')
                saved_current_round = saved_state.get('current_round', 0)
                logger.info(
                    f"读取 run_state.json: current_round={saved_current_round}, "
                    f"total_rounds={saved_total_rounds}, user_max_rounds={saved_user_max_rounds}, "
                    f"runner_status={saved_runner_status}, restored_at={saved_restored_at}"
                )

                # 关键修复：用 restored_at 时间戳作为「快照恢复」的可靠信号
                # 原因：runner_status 在崩溃/异常路径下可能残留为 running/stopping，
                # 旧实现下 restored_from_snapshot 会判 False，导致 --max-rounds
                # 不透传给子脚本，子脚本按 time_config 独立计算 total_rounds 多跑。
                # 兼容：如果 restored_at 不存在（老 run_state 升级场景），回退到
                # runner_status=='idle' 判定，并要求 current_round>0（与「真快照恢复」一致）
                if saved_restored_at:
                    restored_from_snapshot = True
                    logger.info(
                        f"检测到 restored_at={saved_restored_at}，判定为快照恢复场景（可靠信号）"
                    )
                elif saved_runner_status == 'idle' and saved_current_round > 0:
                    restored_from_snapshot = True
                    logger.info("检测到 runner_status=idle 且 current_round>0，判定为快照恢复场景（兼容路径）")
                else:
                    logger.info("未检测到快照恢复标记，判定为普通启动")

                # 修复（恢复/停止后启动重跑 R0 bug）：
                # 场景：恢复快照→启动→停止→再次启动（无 force）时，前端 wasRestored
                # 已清除、start_round 传 0；run_state.json 的 runner_status=idle 且
                # current_round>0 会走"快照恢复场景（兼容路径）"，但 start_round=0
                # 会让子脚本 is_resume=False → 删 DB 从 R0 重跑，已有进度被摧毁。
                # 修复：判定为快照恢复场景且 start_round<=0 时，用 run_state.json 的
                # current_round 作为起始轮次继续（子脚本还会按各平台 runtime_state
                # 精确修正，Twitter/Reddit 各自从自身进度续跑）。
                if restored_from_snapshot and start_round <= 0 and saved_current_round > 0:
                    start_round = int(saved_current_round)
                    actual_start_round = start_round
                    logger.info(
                        f"继续上次进度: start_round 对齐为 run_state current_round={start_round}，"
                        f"子脚本将按各平台 runtime_state 精确修正起始轮次"
                    )

                if saved_total_rounds and saved_total_rounds > 0:
                    total_rounds = saved_total_rounds
                    logger.info(f"从快照恢复 total_rounds: {total_rounds}（原计算值 {int(total_hours * 60 / minutes_per_round)}）")
                else:
                    logger.info(f"run_state.json 中 total_rounds={saved_total_rounds}，使用配置计算值 {int(total_hours * 60 / minutes_per_round)}")
            except Exception as e:
                logger.warning(f"读取快照 total_rounds 失败: {e}，使用计算值")

        # 如果指定了最大轮数，则截断（仅在非快照恢复且显式传了 max_rounds 时）
        # 快照恢复场景下不应截断 total_rounds，因为它代表的是整个模拟应有的总轮数
        # 注意：如果是快照恢复，total_rounds 已经从 run_state.json 恢复过了（可能是被原 max_rounds 截断后的值），
        # 此时不能再用新的 max_rounds 进一步截断，否则可能与快照意图冲突
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                logger.info(f"轮数已截断: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")

        # 确定本次运行最终要保存的 user_max_rounds：
        # - 快照恢复：使用从 run_state.json 恢复的值（保持快照原始意图）
        # - 普通启动：使用用户本次传入的 max_rounds
        final_user_max_rounds = 0
        if restored_from_snapshot and saved_user_max_rounds and saved_user_max_rounds > 0:
            final_user_max_rounds = saved_user_max_rounds
        elif max_rounds is not None and max_rounds > 0:
            final_user_max_rounds = max_rounds

        state = SimulationRunState(
            simulation_id=simulation_id,
            runner_status=RunnerStatus.STARTING,
            total_rounds=total_rounds,
            total_simulation_hours=total_hours,
            started_at=datetime.now().isoformat(),
            current_round=actual_start_round,
            user_max_rounds=final_user_max_rounds,
        )

        # 修复（快照恢复重复读旧 actions bug）：
        # 创建新 state 时未传 twitter_actions_log_position / reddit_actions_log_position 字段，
        # 默认 0 → _save_run_state 会把它写回磁盘，覆盖 restore_snapshot 之前设好的位置。
        # 必须从 disk（已被 restore_snapshot 改写过的）恢复这两个字段，保持 monitor 续读旧 actions.jsonl
        try:
            run_state_file_path = os.path.join(cls.RUN_STATE_DIR, simulation_id, "run_state.json")
            if os.path.exists(run_state_file_path):
                with open(run_state_file_path, 'r', encoding='utf-8') as _f:
                    _saved = json.load(_f)
                state.twitter_actions_log_position = int(_saved.get("twitter_actions_log_position", 0))
                state.reddit_actions_log_position = int(_saved.get("reddit_actions_log_position", 0))
                # 恢复各平台独立轮次（快照恢复场景下 run_state.json 来自快照，
                # 含 twitter_current_round / reddit_current_round 的真实进度）。
                # force 全新启动时 run_state.json 已被 cleanup_simulation_logs 删除，
                # 走不到这里，两平台轮次保持 0，不受影响。
                state.twitter_current_round = int(_saved.get("twitter_current_round", 0))
                state.reddit_current_round = int(_saved.get("reddit_current_round", 0))
                # 修复（恢复后动作计数/模拟时长归零）：monitor 只统计启动后新读到的动作
                # （读取位置已重置到文件末尾，历史 actions 不再过 add_action），
                # 计数从 0 开始 → 前端轮次日志 "A:" 只显示恢复后的动作数。
                # 同理 simulated_hours 只在 round_end 更新 → "T:0h"。
                # 快照恢复场景下 run_state.json 保存了快照时刻的累计值，一并恢复，
                # 使 A: / T: 展示含历史的完整进度。
                state.twitter_actions_count = int(_saved.get("twitter_actions_count", 0))
                state.reddit_actions_count = int(_saved.get("reddit_actions_count", 0))
                state.twitter_simulated_hours = int(_saved.get("twitter_simulated_hours", 0))
                state.reddit_simulated_hours = int(_saved.get("reddit_simulated_hours", 0))
                state.simulated_hours = int(_saved.get("simulated_hours", 0))
                logger.info(
                    f"从 run_state.json 恢复: actions 读取位置 "
                    f"twitter={state.twitter_actions_log_position}, "
                    f"reddit={state.reddit_actions_log_position}; "
                    f"平台轮次 twitter={state.twitter_current_round}, "
                    f"reddit={state.reddit_current_round}; "
                    f"累计动作 twitter={state.twitter_actions_count}, "
                    f"reddit={state.reddit_actions_count}; "
                    f"模拟时长 {state.simulated_hours}h"
                )
        except Exception as _e:
            logger.warning(f"恢复 actions 读取位置失败(继续): {_e}")

        # 修复（快照恢复 recent_actions 残留 bug）：
        # 新启动 = 新一轮模拟，旧 run_state.json 里的 recent_actions（来自前次模拟）会
        # 残留在前端时间轴上显示为"历史动作"。必须清空 recent_actions，强制 monitor 从
        # actions.jsonl 当前位置（已通过 position 字段跳过旧数据）重新同步。
        state.recent_actions.clear()

        cls._save_run_state(state)

        # 自检修复：启动新进程前清理旧的进程/监控线程/共享资源
        # 关键场景：快照恢复（continue 或 start_over）后，原模拟的子进程可能仍在运行
        # （因为 restore_snapshot 不会停止进程），如果不清理会导致：
        #   1. 两个子进程并发写 actions.jsonl / DB，文件冲突
        #   2. 两个监控线程并发写 run_state.json，状态竞争
        #   3. 旧的 stdout 文件句柄被新进程复用，旧监控线程 finally 中可能错误清理新进程的资源
        cls._cleanup_stale_simulation_resources(simulation_id, reason="启动新进程前清理")

        # 如果启用图谱记忆更新，创建更新器
        if enable_graph_memory_update:
            if not graph_id:
                raise ValueError("启用图谱记忆更新时必须提供 graph_id")

            try:
                ZepGraphMemoryManager.create_updater(simulation_id, graph_id)
                cls._graph_memory_enabled[simulation_id] = True
                logger.info(f"已启用图谱记忆更新: simulation_id={simulation_id}, graph_id={graph_id}")
            except Exception as e:
                logger.error(f"创建图谱记忆更新器失败: {e}")
                cls._graph_memory_enabled[simulation_id] = False
        else:
            cls._graph_memory_enabled[simulation_id] = False

        logger.info(f"图谱记忆更新器处理完成: simulation_id={simulation_id}, enabled={cls._graph_memory_enabled.get(simulation_id, False)}")

        # 确定运行哪个脚本（脚本位于 backend/scripts/ 目录）
        if platform == "twitter":
            script_name = "run_twitter_simulation.py"
            state.twitter_running = True
        elif platform == "reddit":
            script_name = "run_reddit_simulation.py"
            state.reddit_running = True
        else:
            script_name = "run_parallel_simulation.py"
            state.twitter_running = True
            state.reddit_running = True
        
        script_path = os.path.join(cls.SCRIPTS_DIR, script_name)
        
        if not os.path.exists(script_path):
            logger.error(f"脚本不存在: {script_path}")
            raise ValueError(f"脚本不存在: {script_path}")

        logger.info(f"脚本检查通过: {script_path}")

        # 创建动作队列
        action_queue = Queue()
        cls._action_queues[simulation_id] = action_queue

        # 启动模拟进程
        try:
            # 构建运行命令，使用完整路径
            # 新的日志结构：
            #   twitter/actions.jsonl - Twitter 动作日志
            #   reddit/actions.jsonl  - Reddit 动作日志
            #   simulation.log        - 主进程日志

            cmd = [
                sys.executable,  # Python解释器
                script_path,
                "--config", config_path,  # 使用完整配置文件路径
            ]

            # 关键修复：快照恢复场景下，必须将快照恢复后的 total_rounds
            # 作为 --max-rounds 传递给脚本。否则脚本会从 simulation_config.json 独立计算
            # total_rounds = (total_hours * 60) // minutes_per_round，如果原始模拟使用了
            # max_rounds 截断（例如 max_rounds=50，config total_rounds=72），快照保存的
            # total_rounds=50，但脚本计算的会是 72，导致 range(start_round, 72) 多跑数轮，
            # 表现为「失去最终轮次的判断，会持续运行下去」。
            #
            # 触发条件：start_round > 0（继续模式） OR restored_from_snapshot（包含 start_over 模式）
            # 修复策略：
            #   - 快照恢复（继续 或 从头开始）：使用 total_rounds（已从 run_state.json 恢复，
            #     可能已被原 max_rounds 截断）作为 --max-rounds
            #   - 正常启动（无快照）：使用用户传入的 max_rounds 作为 --max-rounds
            # 关键：start_round > 0 同时也意味着「快照 resume 模式」
            #   → 子脚本 run_parallel_simulation.py 在 start_round>0 且 DB 已存在时会
            #     跳过 DB 删除 + env.reset() + signup + 初始帖子,直接通过
            #     platform.running() + connect_platform_channel 接管 snapshot DB
            #   → 这是真正的快照恢复,而不是「重跑」从某个轮次开始
            if start_round > 0 or restored_from_snapshot:
                # 快照恢复：使用已恢复的 total_rounds（与 state.total_rounds 一致）
                cmd.extend(["--max-rounds", str(total_rounds)])
                if start_round > 0:
                    cmd.extend(["--start-round", str(start_round)])
                logger.info(
                    f"快照恢复场景：传递 --max-rounds {total_rounds}"
                    f"{' 和 --start-round ' + str(start_round) if start_round > 0 else '（start_over 模式，从头开始）'} "
                    f"（脚本将基于 max_rounds 截断 total_rounds，确保与快照保存的轮数一致）"
                )
                if start_round > 0:
                    # 关键 resume 日志:子脚本将根据 (start_round > 0 且 DB 已存在) 判定进入 resume 模式
                    logger.info(
                        f"【Resume】start_round={start_round} > 0 → "
                        f"子脚本将进入 resume 模式:"
                        f"不删 DB / 不 reset / 不 signup / 不发初始帖;"
                        f"从 snapshot DB 接续用户/帖子/关注,"
                        f"Twitter 恢复 sandbox_clock.time_step、Reddit 恢复 start_time"
                    )
            elif max_rounds is not None and max_rounds > 0:
                cmd.extend(["--max-rounds", str(max_rounds)])

            logger.info(f"构建启动命令: {' '.join(cmd[:5])}...")

            # 创建主日志文件，避免 stdout/stderr 管道缓冲区满导致进程阻塞
            main_log_path = os.path.join(sim_dir, "simulation.log")
            main_log_file = open(main_log_path, 'w', encoding='utf-8')
            
            # 设置子进程环境变量，确保 Windows 上使用 UTF-8 编码
            # 这可以修复第三方库（如 OASIS）读取文件时未指定编码的问题
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'  # Python 3.7+ 支持，让所有 open() 默认使用 UTF-8
            env['PYTHONIOENCODING'] = 'utf-8'  # 确保 stdout/stderr 使用 UTF-8
            
            # 设置工作目录为模拟目录（数据库等文件会生成在此）
            # 使用 start_new_session=True 创建新的进程组，确保可以通过 os.killpg 终止所有子进程
            logger.info(f"准备启动子进程: cwd={sim_dir}")
            process = subprocess.Popen(
                cmd,
                cwd=sim_dir,
                stdout=main_log_file,
                stderr=subprocess.STDOUT,  # stderr 也写入同一个文件
                text=True,
                encoding='utf-8',  # 显式指定编码
                bufsize=1,
                env=env,  # 传递带有 UTF-8 设置的环境变量
                start_new_session=True,  # 创建新进程组，确保服务器关闭时能终止所有相关进程
            )
            logger.info(f"子进程启动成功: pid={process.pid}")
            
            # 保存文件句柄以便后续关闭
            cls._stdout_files[simulation_id] = main_log_file
            cls._stderr_files[simulation_id] = None  # 不再需要单独的 stderr
            
            state.process_pid = process.pid
            state.runner_status = RunnerStatus.RUNNING
            cls._processes[simulation_id] = process
            cls._save_run_state(state)

            # 关键修复：清掉 restored_at 标记
            # restore_snapshot 写入的 restored_at 在新进程成功启动后失效，
            # 否则下次普通启动会再次被误判为「快照恢复场景」并错误透传 max_rounds/start_round
            # 直接修改 run_state.json（state 内存对象不持有这两个字段，下次 save 会覆盖）
            try:
                if os.path.exists(run_state_file):
                    with open(run_state_file, 'r', encoding='utf-8') as f:
                        _rs = json.load(f)
                    if _rs.get("restored_at") or _rs.get("restored_snapshot_name"):
                        _rs.pop("restored_at", None)
                        _rs.pop("restored_snapshot_name", None)
                        atomic_write_json(run_state_file, _rs)
                        logger.info("已清掉 restored_at 标记（本次恢复已完成使命）")
            except Exception as _e:
                logger.warning(f"清掉 restored_at 失败: {_e}（下次启动可能误判，下次正常启动时也会被 _save_run_state 覆盖）")
            
            # Capture locale before spawning monitor thread
            current_locale = get_locale()

            # 启动监控线程
            monitor_thread = threading.Thread(
                target=cls._monitor_simulation,
                args=(simulation_id, current_locale),
                daemon=True
            )
            monitor_thread.start()
            cls._monitor_threads[simulation_id] = monitor_thread
            
            logger.info(f"模拟启动成功: {simulation_id}, pid={process.pid}, platform={platform}")
            
        except Exception as e:
            # 修复（启动异常孤儿进程）：Popen 成功之后、monitor 正常接管之前，
            # 任何异常（如 _save_run_state 写盘失败）都会走到这里。旧实现只标
            # FAILED 就 raise——子进程继续在后台写文件/调 LLM，而 UI 已显示失败，
            # 形成幽灵进程。此处统一兜底：杀掉已启动的子进程并清理资源
            # （正常路径这些清理由 monitor 线程的 finally 负责；monitor 未启动时无人清理）。
            orphan = cls._processes.get(simulation_id)
            if orphan is not None and orphan.poll() is None:
                try:
                    cls._terminate_process(orphan, simulation_id, timeout=5)
                    logger.warning(f"启动失败，已终止孤儿子进程: pid={orphan.pid}")
                except Exception as kill_err:
                    logger.error(
                        f"终止孤儿子进程失败（可能残留，请手动结束 pid={orphan.pid}）: {kill_err}"
                    )
            cls._processes.pop(simulation_id, None)
            cls._monitor_threads.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            for _files_dict in (cls._stdout_files, cls._stderr_files):
                _fh = _files_dict.pop(simulation_id, None)
                if _fh is not None:
                    try:
                        _fh.close()
                    except Exception:
                        pass
            if cls._graph_memory_enabled.pop(simulation_id, None):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                except Exception:
                    pass

            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)
            raise
        
        return state
    
    @classmethod
    def _monitor_simulation(cls, simulation_id: str, locale: str = 'zh'):
        """监控模拟进程，解析动作日志"""
        set_locale(locale)
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        # 新的日志结构：分平台的动作日志
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")

        process = cls._processes.get(simulation_id)
        state = cls.get_run_state(simulation_id)

        if not process or not state:
            return

        # 修复（快照恢复重复读旧 actions bug）：
        # 从 state 恢复 position，避免从 0 重读旧 actions.jsonl
        twitter_position = state.twitter_actions_log_position or 0
        reddit_position = state.reddit_actions_log_position or 0
        twitter_last_size = -1  # 性能优化：文件大小短路；未增长则跳过 read+parse
        reddit_last_size = -1
        last_save_time = 0  # 上次保存时间戳
        save_interval = 5  # 至少间隔 5 秒才保存
        # 优化 S1：周期性自动快照 —— 长跑模拟抗风险
        # 每 SIMULATION_AUTO_SNAPSHOT_INTERVAL_ROUNDS 轮触发一次 snapshot
        # 仅保留最近 SIMULATION_AUTO_SNAPSHOTS_KEEP 个 auto 快照
        # 修复（NameError）：之前在 _monitor_simulation 闭包里定义，_read_action_log 是
        # @classmethod 拿不到。现在统一在 state._last_snapshot_round 上追踪
        state._last_snapshot_round = -1

        try:
            while process.poll() is None:  # 进程仍在运行
                changed = False
                # 读取 Twitter 动作日志
                # 性能优化：先看文件大小，上次已读到文件末尾则跳过 open + read
                # 依据：子进程 append-only 写，文件只增不减；position == size ⇒ 无新数据
                if os.path.exists(twitter_actions_log):
                    try:
                        cur_size = os.path.getsize(twitter_actions_log)
                    except OSError:
                        cur_size = 0
                    if cur_size != twitter_last_size:
                        new_position = cls._read_action_log(
                            twitter_actions_log, twitter_position, state, "twitter"
                        )
                        if new_position != twitter_position:
                            twitter_position = new_position
                            # 修复：把 position 持久化到 state，monitor 重启时不会重读旧 actions
                            state.twitter_actions_log_position = twitter_position
                            changed = True
                        # 读完后用 size 更新 last_size，下次 size 不变即短路
                        try:
                            twitter_last_size = os.path.getsize(twitter_actions_log)
                        except OSError:
                            twitter_last_size = new_position

                # 读取 Reddit 动作日志
                if os.path.exists(reddit_actions_log):
                    try:
                        cur_size = os.path.getsize(reddit_actions_log)
                    except OSError:
                        cur_size = 0
                    if cur_size != reddit_last_size:
                        new_position = cls._read_action_log(
                            reddit_actions_log, reddit_position, state, "reddit"
                        )
                        if new_position != reddit_position:
                            reddit_position = new_position
                            # 修复：把 position 持久化到 state，monitor 重启时不会重读旧 actions
                            state.reddit_actions_log_position = reddit_position
                            changed = True
                        try:
                            reddit_last_size = os.path.getsize(reddit_actions_log)
                        except OSError:
                            reddit_last_size = new_position

                # 只在数据有变化时保存，且间隔至少 5 秒（减少磁盘 I/O）
                current_time = time.time()
                if (changed or current_time - last_save_time >= save_interval):
                    cls._save_run_state(state)
                    last_save_time = current_time

                time.sleep(2)
            
            # 进程结束后，最后读取一次日志
            # 修复（终读 position 未持久化）：旧实现丢弃 _read_action_log 的返回值——
            # 最后一批动作已进计数（actions_count +，卡片时间轴），但 position 停留在
            # 上次循环保存的旧值。当前终态后无人再读看似无影响，但任何后续复用该
            # position 的路径（如 monitor 重启、快照恢复前重算计数）都会重复读最后
            # 一批动作。与循环内处理保持同构：接住返回值写回 state 并持久化。
            if os.path.exists(twitter_actions_log):
                _final_pos = cls._read_action_log(twitter_actions_log, twitter_position, state, "twitter")
                if _final_pos != twitter_position:
                    twitter_position = _final_pos
                    state.twitter_actions_log_position = twitter_position
            if os.path.exists(reddit_actions_log):
                _final_pos = cls._read_action_log(reddit_actions_log, reddit_position, state, "reddit")
                if _final_pos != reddit_position:
                    reddit_position = _final_pos
                    state.reddit_actions_log_position = reddit_position
            
            # 进程结束
            exit_code = process.returncode

            # 修复（正常停止被误标 FAILED）：用户主动 stop 时 taskkill 产生的退出码必然非 0，
            # 旧实现只看 exit_code → 每次正常停止都被标记为 FAILED + 写入吓人的错误信息
            # + 误触发 crash_ 崩溃快照污染快照列表。
            # 判定依据：stop_simulation 与本监控线程共享同一个 state 对象（get_run_state
            # 走内存缓存），用户停止时 stop_simulation 先置 STOPPING（杀进程前）再置
            # STOPPED（杀进程后），两者任一出现即为用户主动停止。
            user_stopped = state.runner_status in (RunnerStatus.STOPPING, RunnerStatus.STOPPED)

            if user_stopped:
                # 用户停止：退出码无诊断意义，不改写状态、不写错误、不建崩溃快照
                logger.info(f"进程因用户停止而退出: {simulation_id}, exit_code={exit_code}（不标记为失败）")
                if state.runner_status == RunnerStatus.STOPPING:
                    # 兜底：stop_simulation 中途异常未终结时，由 monitor 终结为 STOPPED，
                    # 确保 _sync_manager_state 能把 STOPPED 同步进 state.json
                    state.runner_status = RunnerStatus.STOPPED
                    state.completed_at = datetime.now().isoformat()
            elif exit_code == 0:
                state.runner_status = RunnerStatus.COMPLETED
                state.completed_at = datetime.now().isoformat()
                logger.info(f"模拟完成: {simulation_id}")
            else:
                state.runner_status = RunnerStatus.FAILED
                # 从主日志文件读取错误信息
                main_log_path = os.path.join(sim_dir, "simulation.log")
                error_info = ""
                try:
                    if os.path.exists(main_log_path):
                        with open(main_log_path, 'r', encoding='utf-8') as f:
                            error_info = f.read()[-2000:]  # 取最后2000字符
                except Exception:
                    pass
                state.error = f"进程退出码: {exit_code}, 错误: {error_info}"
                logger.error(f"模拟失败: {simulation_id}, error={state.error}")
            
            state.twitter_running = False
            state.reddit_running = False
            cls._save_run_state(state)

            # 同步更新 SimulationManager 的 state.json
            cls._sync_manager_state(simulation_id, state)

            # 必修 8：进程退出时同步更新 env_status.json 到 stopped
            # 旧实现：子进程退出后 env_status.json 仍保留 stale 'alive' 状态
            # 导致 check_env_alive 误判 alive（必修 7 已有时间戳兜底延迟 60s）
            # 这里显式更新到 stopped，让 API 立即识别"子进程已死"，走 offline fallback
            try:
                from .simulation_ipc import SimulationIPCClient
                ipc_client = SimulationIPCClient(sim_dir)
                ipc_client._update_env_status("stopped")
                logger.debug(f"已更新 env_status.json: {simulation_id} -> stopped")
            except Exception as e:
                logger.warning(f"更新 env_status.json 失败（不影响主流程）: {e}")

            # 优化 S2：进程异常退出时自动 snapshot（崩溃抗风险）
            # 仅在 exit_code != 0 时触发，0 是正常完成（已有前端 on_complete 快照）
            # 修复（正常停止被误标 FAILED 的同源问题）：用户主动停止（taskkill）退出码也非 0，
            # 但那不是崩溃——此时强制落 crash_ 快照只会污染快照列表。用户停止由
            # stop_simulation 已有的 pre_restore / 正常流程覆盖，无需崩溃快照。
            # snapshot 失败不能阻塞原异常路径
            if exit_code != 0 and not user_stopped:
                try:
                    snap_name = f"crash_r{state.current_round}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    cls.create_snapshot(simulation_id, snapshot_name=snap_name)
                    logger.info(f"崩溃自动快照: {simulation_id} @ round {state.current_round}, exit_code={exit_code}")
                except Exception as snap_err:
                    logger.warning(f"崩溃快照失败（已跳过）: {snap_err}")

        except Exception as e:
            logger.error(f"监控线程异常: {simulation_id}, error={str(e)}")
            state.runner_status = RunnerStatus.FAILED
            state.error = str(e)
            cls._save_run_state(state)

            # 同步更新 SimulationManager 的 state.json
            cls._sync_manager_state(simulation_id, state)

            # 必修 8：监控线程异常退出时也更新 env_status 到 stopped
            try:
                from .simulation_ipc import SimulationIPCClient
                ipc_client = SimulationIPCClient(sim_dir)
                ipc_client._update_env_status("stopped")
            except Exception:
                pass  # 已 try/except 包裹，吞掉避免影响 finally

            # 优化 S2：监控线程自身异常也尝试 snapshot（兜底抗风险）
            try:
                snap_name = f"crash_r{state.current_round}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                cls.create_snapshot(simulation_id, snapshot_name=snap_name)
                logger.info(f"监控线程异常自动快照: {simulation_id} @ round {state.current_round}")
            except Exception as snap_err:
                logger.warning(f"监控异常快照失败（已跳过）: {snap_err}")
        
        finally:
            # 停止图谱记忆更新器
            if cls._graph_memory_enabled.get(simulation_id, False):
                try:
                    ZepGraphMemoryManager.stop_updater(simulation_id)
                    logger.info(f"已停止图谱记忆更新: simulation_id={simulation_id}")
                except Exception as e:
                    logger.error(f"停止图谱记忆更新器失败: {e}")
                cls._graph_memory_enabled.pop(simulation_id, None)
            
            # 清理进程资源
            cls._processes.pop(simulation_id, None)
            cls._action_queues.pop(simulation_id, None)
            
            # 关闭日志文件句柄
            if simulation_id in cls._stdout_files:
                try:
                    cls._stdout_files[simulation_id].close()
                except Exception:
                    pass
                cls._stdout_files.pop(simulation_id, None)
            if simulation_id in cls._stderr_files and cls._stderr_files[simulation_id]:
                try:
                    cls._stderr_files[simulation_id].close()
                except Exception:
                    pass
                cls._stderr_files.pop(simulation_id, None)
    
    @classmethod
    def _read_action_log(
        cls, 
        log_path: str, 
        position: int, 
        state: SimulationRunState,
        platform: str
    ) -> int:
        """
        读取动作日志文件
        
        Args:
            log_path: 日志文件路径
            position: 上次读取位置
            state: 运行状态对象
            platform: 平台名称 (twitter/reddit)
            
        Returns:
            新的读取位置
        """
        # 检查是否启用了图谱记忆更新
        graph_memory_enabled = cls._graph_memory_enabled.get(state.simulation_id, False)
        graph_updater = None
        if graph_memory_enabled:
            graph_updater = ZepGraphMemoryManager.get_updater(state.simulation_id)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                f.seek(position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            action_data = json.loads(line)
                            
                            # 处理事件类型的条目
                            if "event_type" in action_data:
                                event_type = action_data.get("event_type")
                                
                                # 检测 simulation_end 事件，标记平台已完成
                                if event_type == "simulation_end":
                                    if platform == "twitter":
                                        state.twitter_completed = True
                                        state.twitter_running = False
                                        logger.info(f"Twitter 模拟已完成: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    elif platform == "reddit":
                                        state.reddit_completed = True
                                        state.reddit_running = False
                                        logger.info(f"Reddit 模拟已完成: {state.simulation_id}, total_rounds={action_data.get('total_rounds')}, total_actions={action_data.get('total_actions')}")
                                    
                                    # 检查是否所有启用的平台都已完成
                                    # 如果只运行了一个平台，只检查那个平台
                                    # 如果运行了两个平台，需要两个都完成
                                    all_completed = cls._check_all_platforms_completed(state)
                                    if all_completed:
                                        state.runner_status = RunnerStatus.COMPLETED
                                        state.completed_at = datetime.now().isoformat()
                                        logger.info(f"所有平台模拟已完成: {state.simulation_id}")
                                
                                # 更新轮次信息（从 round_end 事件）
                                elif event_type == "round_end":
                                    round_num = action_data.get("round", 0)
                                    simulated_hours = action_data.get("simulated_hours", 0)

                                    # 更新各平台独立的轮次和时间
                                    if platform == "twitter":
                                        if round_num > state.twitter_current_round:
                                            state.twitter_current_round = round_num
                                        state.twitter_simulated_hours = simulated_hours
                                    elif platform == "reddit":
                                        if round_num > state.reddit_current_round:
                                            state.reddit_current_round = round_num
                                        state.reddit_simulated_hours = simulated_hours

                                    # 总体轮次取两个平台的最大值
                                    if round_num > state.current_round:
                                        state.current_round = round_num
                                    # 总体时间取两个平台的最大值
                                    state.simulated_hours = max(state.twitter_simulated_hours, state.reddit_simulated_hours)

                                    # 优化 S1：周期性自动快照（每 N 轮触发一次）
                                    # 业务不变性：snapshot 是"过去数据"完整保存，恢复后从同 start_round 继续
                                    # 修复（NameError + 持久化）：从 state._last_snapshot_round 读取
                                    # 该字段已在 dataclass 声明（默认 -1），且 to_dict 持久化 + _load_run_state 恢复
                                    # 这里不再做 hasattr 防御，避免死代码
                                    if Config.SIMULATION_AUTO_SNAPSHOT_ENABLED:
                                        interval = Config.SIMULATION_AUTO_SNAPSHOT_INTERVAL_ROUNDS
                                        if interval > 0 and round_num > 0 and round_num - state._last_snapshot_round >= interval:
                                            try:
                                                snap_name = f"auto_r{round_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                                cls.create_snapshot(state.simulation_id, snapshot_name=snap_name)
                                                cls._cleanup_old_auto_snapshots(state.simulation_id)
                                                state._last_snapshot_round = round_num
                                                logger.info(f"周期性自动快照: {state.simulation_id} @ round {round_num}")
                                            except Exception as snap_err:
                                                # snapshot 失败不能阻塞模拟主流程
                                                logger.warning(f"周期性快照失败（已跳过）: {snap_err}")

                                continue
                            
                            action = AgentAction(
                                round_num=action_data.get("round", 0),
                                timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                                platform=platform,
                                agent_id=action_data.get("agent_id", 0),
                                agent_name=action_data.get("agent_name", ""),
                                action_type=action_data.get("action_type", ""),
                                action_args=action_data.get("action_args", {}),
                                result=action_data.get("result"),
                                success=action_data.get("success", True),
                            )
                            state.add_action(action)
                            
                            # 更新轮次
                            if action.round_num and action.round_num > state.current_round:
                                state.current_round = action.round_num
                            
                            # 如果启用了图谱记忆更新，将活动发送到Zep
                            if graph_updater:
                                graph_updater.add_activity_from_dict(action_data, platform)
                            
                        except json.JSONDecodeError:
                            pass
                # 修复（updated_at 不随事件摄入刷新）：
                # updated_at 原只在 add_action（新 agent 动作）刷新，事件类行
                # （round_end / simulation_end）更新轮次、完成标志但不刷新时间戳。
                # 恢复"两平台已完成"的快照时零新动作，updated_at 永不变 →
                # /run-status 的 B3 缓存 key 不变，前端轮询永远命中启动时的旧响应。
                # 摄入了新日志行（position 前进）即视为状态更新，刷新 updated_at。
                if f.tell() > position:
                    state.updated_at = datetime.now().isoformat()
                return f.tell()
        except Exception as e:
            logger.warning(f"读取动作日志失败: {log_path}, error={e}")
            return position
    
    @classmethod
    def _check_all_platforms_completed(cls, state: SimulationRunState) -> bool:
        """
        检查所有启用的平台是否都已完成模拟
        
        通过检查对应的 actions.jsonl 文件是否存在来判断平台是否被启用
        
        Returns:
            True 如果所有启用的平台都已完成
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, state.simulation_id)
        twitter_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        reddit_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        
        # 检查哪些平台被启用（通过文件是否存在判断）
        twitter_enabled = os.path.exists(twitter_log)
        reddit_enabled = os.path.exists(reddit_log)
        
        # 如果平台被启用但未完成，则返回 False
        if twitter_enabled and not state.twitter_completed:
            return False
        if reddit_enabled and not state.reddit_completed:
            return False
        
        # 至少有一个平台被启用且已完成
        return twitter_enabled or reddit_enabled
    
    @classmethod
    def _terminate_process(cls, process: subprocess.Popen, simulation_id: str, timeout: int = 10):
        """
        跨平台终止进程及其子进程
        
        Args:
            process: 要终止的进程
            simulation_id: 模拟ID（用于日志）
            timeout: 等待进程退出的超时时间（秒）
        """
        if IS_WINDOWS:
            # Windows: 使用 taskkill 命令终止进程树
            # /F = 强制终止, /T = 终止进程树（包括子进程）
            logger.info(f"终止进程树 (Windows): simulation={simulation_id}, pid={process.pid}")
            try:
                # 先尝试优雅终止
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T'],
                    capture_output=True,
                    timeout=5
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    logger.warning(f"进程未响应，强制终止: {simulation_id}")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(process.pid), '/T'],
                        capture_output=True,
                        timeout=5
                    )
                    process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"taskkill 失败，尝试 terminate: {e}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        else:
            # Unix: 使用进程组终止
            # 由于使用了 start_new_session=True，进程组 ID 等于主进程 PID
            pgid = os.getpgid(process.pid)
            logger.info(f"终止进程组 (Unix): simulation={simulation_id}, pgid={pgid}")
            
            # 先发送 SIGTERM 给整个进程组
            os.killpg(pgid, signal.SIGTERM)
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 如果超时后还没结束，强制发送 SIGKILL
                logger.warning(f"进程组未响应 SIGTERM，强制终止: {simulation_id}")
                os.killpg(pgid, signal.SIGKILL)
                process.wait(timeout=5)
    
    @classmethod
    def stop_simulation(cls, simulation_id: str) -> SimulationRunState:
        """停止模拟"""
        state = cls.get_run_state(simulation_id)
        if not state:
            raise ValueError(f"模拟不存在: {simulation_id}")
        
        if state.runner_status not in [RunnerStatus.RUNNING, RunnerStatus.PAUSED]:
            raise ValueError(f"模拟未在运行: {simulation_id}, status={state.runner_status}")
        
        state.runner_status = RunnerStatus.STOPPING
        cls._save_run_state(state)
        
        # 终止进程
        process = cls._processes.get(simulation_id)
        if process and process.poll() is None:
            try:
                cls._terminate_process(process, simulation_id)
            except ProcessLookupError:
                # 进程已经不存在
                pass
            except Exception as e:
                logger.error(f"终止进程组失败: {simulation_id}, error={e}")
                # 回退到直接终止进程
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
        
        state.runner_status = RunnerStatus.STOPPED
        state.twitter_running = False
        state.reddit_running = False
        state.completed_at = datetime.now().isoformat()
        cls._save_run_state(state)
        
        # 停止图谱记忆更新器
        if cls._graph_memory_enabled.get(simulation_id, False):
            try:
                ZepGraphMemoryManager.stop_updater(simulation_id)
                logger.info(f"已停止图谱记忆更新: simulation_id={simulation_id}")
            except Exception as e:
                logger.error(f"停止图谱记忆更新器失败: {e}")
            cls._graph_memory_enabled.pop(simulation_id, None)
        
        logger.info(f"模拟已停止: {simulation_id}")
        return state
    
    @classmethod
    def _read_actions_from_file(
        cls,
        file_path: str,
        default_platform: Optional[str] = None,
        platform_filter: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        从单个动作文件中读取动作
        
        Args:
            file_path: 动作日志文件路径
            default_platform: 默认平台（当动作记录中没有 platform 字段时使用）
            platform_filter: 过滤平台
            agent_id: 过滤 Agent ID
            round_num: 过滤轮次
        """
        if not os.path.exists(file_path):
            return []
        
        actions = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # 跳过非动作记录（如 simulation_start, round_start, round_end 等事件）
                    if "event_type" in data:
                        continue
                    
                    # 跳过没有 agent_id 的记录（非 Agent 动作）
                    if "agent_id" not in data:
                        continue
                    
                    # 获取平台：优先使用记录中的 platform，否则使用默认平台
                    record_platform = data.get("platform") or default_platform or ""
                    
                    # 过滤
                    if platform_filter and record_platform != platform_filter:
                        continue
                    if agent_id is not None and data.get("agent_id") != agent_id:
                        continue
                    if round_num is not None and data.get("round") != round_num:
                        continue
                    
                    actions.append(AgentAction(
                        round_num=data.get("round", 0),
                        timestamp=data.get("timestamp", ""),
                        platform=record_platform,
                        agent_id=data.get("agent_id", 0),
                        agent_name=data.get("agent_name", ""),
                        action_type=data.get("action_type", ""),
                        action_args=data.get("action_args", {}),
                        result=data.get("result"),
                        success=data.get("success", True),
                    ))
                    
                except json.JSONDecodeError:
                    continue
        
        return actions
    
    @classmethod
    def get_all_actions(
        cls,
        simulation_id: str,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        获取所有平台的完整动作历史（无分页限制）
        
        Args:
            simulation_id: 模拟ID
            platform: 过滤平台（twitter/reddit）
            agent_id: 过滤Agent
            round_num: 过滤轮次
            
        Returns:
            完整的动作列表（按时间戳排序，新的在前）
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        actions = []
        
        # 读取 Twitter 动作文件（根据文件路径自动设置 platform 为 twitter）
        twitter_actions_log = os.path.join(sim_dir, "twitter", "actions.jsonl")
        if not platform or platform == "twitter":
            actions.extend(cls._read_actions_from_file(
                twitter_actions_log,
                default_platform="twitter",  # 自动填充 platform 字段
                platform_filter=platform,
                agent_id=agent_id, 
                round_num=round_num
            ))
        
        # 读取 Reddit 动作文件（根据文件路径自动设置 platform 为 reddit）
        reddit_actions_log = os.path.join(sim_dir, "reddit", "actions.jsonl")
        if not platform or platform == "reddit":
            actions.extend(cls._read_actions_from_file(
                reddit_actions_log,
                default_platform="reddit",  # 自动填充 platform 字段
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            ))
        
        # 如果分平台文件不存在，尝试读取旧的单一文件格式
        if not actions:
            actions_log = os.path.join(sim_dir, "actions.jsonl")
            actions = cls._read_actions_from_file(
                actions_log,
                default_platform=None,  # 旧格式文件中应该有 platform 字段
                platform_filter=platform,
                agent_id=agent_id,
                round_num=round_num
            )
        
        # 按时间戳排序（新的在前）
        actions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return actions
    
    @classmethod
    def get_actions(
        cls,
        simulation_id: str,
        limit: int = 100,
        offset: int = 0,
        platform: Optional[str] = None,
        agent_id: Optional[int] = None,
        round_num: Optional[int] = None
    ) -> List[AgentAction]:
        """
        获取动作历史（带分页）
        
        Args:
            simulation_id: 模拟ID
            limit: 返回数量限制
            offset: 偏移量
            platform: 过滤平台
            agent_id: 过滤Agent
            round_num: 过滤轮次
            
        Returns:
            动作列表
        """
        actions = cls.get_all_actions(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        # 分页
        return actions[offset:offset + limit]
    
    @classmethod
    def get_timeline(
        cls,
        simulation_id: str,
        start_round: int = 0,
        end_round: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取模拟时间线（按轮次汇总）
        
        Args:
            simulation_id: 模拟ID
            start_round: 起始轮次
            end_round: 结束轮次
            
        Returns:
            每轮的汇总信息
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        # 按轮次分组
        rounds: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            round_num = action.round_num
            
            if round_num < start_round:
                continue
            if end_round is not None and round_num > end_round:
                continue
            
            if round_num not in rounds:
                rounds[round_num] = {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "active_agents": set(),
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            r = rounds[round_num]
            
            if action.platform == "twitter":
                r["twitter_actions"] += 1
            else:
                r["reddit_actions"] += 1
            
            r["active_agents"].add(action.agent_id)
            r["action_types"][action.action_type] = r["action_types"].get(action.action_type, 0) + 1
            r["last_action_time"] = action.timestamp
        
        # 转换为列表
        result = []
        for round_num in sorted(rounds.keys()):
            r = rounds[round_num]
            result.append({
                "round_num": round_num,
                "twitter_actions": r["twitter_actions"],
                "reddit_actions": r["reddit_actions"],
                "total_actions": r["twitter_actions"] + r["reddit_actions"],
                "active_agents_count": len(r["active_agents"]),
                "active_agents": list(r["active_agents"]),
                "action_types": r["action_types"],
                "first_action_time": r["first_action_time"],
                "last_action_time": r["last_action_time"],
            })
        
        return result
    
    @classmethod
    def get_agent_stats(cls, simulation_id: str) -> List[Dict[str, Any]]:
        """
        获取每个Agent的统计信息
        
        Returns:
            Agent统计列表
        """
        actions = cls.get_actions(simulation_id, limit=10000)
        
        agent_stats: Dict[int, Dict[str, Any]] = {}
        
        for action in actions:
            agent_id = action.agent_id
            
            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": action.agent_name,
                    "total_actions": 0,
                    "twitter_actions": 0,
                    "reddit_actions": 0,
                    "action_types": {},
                    "first_action_time": action.timestamp,
                    "last_action_time": action.timestamp,
                }
            
            stats = agent_stats[agent_id]
            stats["total_actions"] += 1
            
            if action.platform == "twitter":
                stats["twitter_actions"] += 1
            else:
                stats["reddit_actions"] += 1
            
            stats["action_types"][action.action_type] = stats["action_types"].get(action.action_type, 0) + 1
            stats["last_action_time"] = action.timestamp
        
        # 按总动作数排序
        result = sorted(agent_stats.values(), key=lambda x: x["total_actions"], reverse=True)
        
        return result
    
    @classmethod
    def cleanup_simulation_logs(cls, simulation_id: str) -> Dict[str, Any]:
        """
        清理模拟的运行日志（用于强制重新开始模拟）

        会删除以下文件：
        - run_state.json
        - twitter/actions.jsonl
        - reddit/actions.jsonl
        - simulation.log
        - stdout.log / stderr.log
        - twitter_simulation.db / twitter_simulation_*.db（模拟数据库）
        - reddit_simulation.db / reddit_simulation_*.db（模拟数据库）
        - env_status.json（环境状态）
        - ipc_commands/ ipc_responses/ 中的所有 .json（IPC 残留）

        注意：不会删除：
        - snapshots/ 目录（用户快照保留，让用户能从快照恢复）
        - 配置文件（simulation_config.json）和 profile 文件

        修复：原 docstring 说"清理历史快照"是错的，实际实现保留快照。
        这是合理的业务行为：用户 force 重启后，可能想从某个快照恢复进度。

        Args:
            simulation_id: 模拟ID

        Returns:
            清理结果信息
        """
        import shutil
        import glob

        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return {"success": True, "message": "模拟目录不存在，无需清理"}

        cleaned_files = []
        errors = []

        # 要删除的文件列表（包括数据库文件）
        files_to_delete = [
            "run_state.json",
            "simulation.log",
            "stdout.log",
            "stderr.log",
            "twitter_simulation.db",  # Twitter 平台数据库
            "reddit_simulation.db",   # Reddit 平台数据库
            "env_status.json",        # 环境状态文件
        ]

        # 删除精确匹配的文件
        for filename in files_to_delete:
            file_path = os.path.join(sim_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_files.append(filename)
                except Exception as e:
                    errors.append(f"删除 {filename} 失败: {str(e)}")

        # 删除 glob 匹配的数据库文件（与 create_snapshot 中的快照保存保持一致）
        db_patterns = [
            "twitter_simulation_*.db",
            "reddit_simulation_*.db",
        ]
        for db_pattern in db_patterns:
            matching_files = glob.glob(os.path.join(sim_dir, db_pattern))
            for db_path in matching_files:
                db_name = os.path.basename(db_path)
                try:
                    os.remove(db_path)
                    cleaned_files.append(db_name)
                except Exception as e:
                    errors.append(f"删除 {db_name} 失败: {str(e)}")

        # 清理平台目录中的动作日志
        dirs_to_clean = ["twitter", "reddit"]
        for dir_name in dirs_to_clean:
            dir_path = os.path.join(sim_dir, dir_name)
            if os.path.exists(dir_path):
                for file_in_dir in ["actions.jsonl", "profiles.json"]:
                    actions_file = os.path.join(dir_path, file_in_dir)
                    if os.path.exists(actions_file):
                        try:
                            os.remove(actions_file)
                            cleaned_files.append(f"{dir_name}/{file_in_dir}")
                        except Exception as e:
                            errors.append(f"删除 {dir_name}/{file_in_dir} 失败: {str(e)}")

        # 关键修复：清理 IPC 命令/响应残留（BUG-7/8）— 调用共享 helper
        cls._cleanup_ipc_dirs(simulation_id)
        cleaned_files.append("ipc_commands/")
        cleaned_files.append("ipc_responses/")

        # 清理 agent memory + Python/OASIS random state + runtime state 目录,
        # 避免 force=true 重启后,上一次模拟的 agent memory / random state 污染新模拟。
        for subdir in ("agent_memory", "random_state", "runtime_state"):
            subdir_path = os.path.join(sim_dir, subdir)
            if os.path.isdir(subdir_path):
                try:
                    shutil.rmtree(subdir_path)
                    cleaned_files.append(f"{subdir}/")
                except Exception as e:
                    errors.append(f"删除 {subdir}/ 失败: {str(e)}")

        # 清理内存中的运行状态
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]

        logger.info(f"清理模拟日志完成: {simulation_id}, 删除文件: {cleaned_files}")

        return {
            "success": len(errors) == 0,
            "cleaned_files": cleaned_files,
            "errors": errors if errors else None
        }
    
    # 防止重复清理的标志
    _cleanup_done = False
    
    @classmethod
    def cleanup_all_simulations(cls):
        """
        清理所有运行中的模拟进程
        
        在服务器关闭时调用，确保所有子进程被终止
        """
        # 防止重复清理
        if cls._cleanup_done:
            return
        cls._cleanup_done = True
        
        # 检查是否有内容需要清理（避免空进程的进程打印无用日志）
        has_processes = bool(cls._processes)
        has_updaters = bool(cls._graph_memory_enabled)
        
        if not has_processes and not has_updaters:
            return  # 没有需要清理的内容，静默返回
        
        logger.info("正在清理所有模拟进程...")
        
        # 首先停止所有图谱记忆更新器（stop_all 内部会打印日志）
        try:
            ZepGraphMemoryManager.stop_all()
        except Exception as e:
            logger.error(f"停止图谱记忆更新器失败: {e}")
        cls._graph_memory_enabled.clear()
        
        # 复制字典以避免在迭代时修改
        processes = list(cls._processes.items())
        
        for simulation_id, process in processes:
            try:
                if process.poll() is None:  # 进程仍在运行
                    logger.info(f"终止模拟进程: {simulation_id}, pid={process.pid}")
                    
                    try:
                        # 使用跨平台的进程终止方法
                        cls._terminate_process(process, simulation_id, timeout=5)
                    except (ProcessLookupError, OSError):
                        # 进程可能已经不存在，尝试直接终止
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except Exception:
                            process.kill()
                    
                    # 更新 run_state.json
                    state = cls.get_run_state(simulation_id)
                    if state:
                        state.runner_status = RunnerStatus.STOPPED
                        state.twitter_running = False
                        state.reddit_running = False
                        state.completed_at = datetime.now().isoformat()
                        state.error = "服务器关闭，模拟被终止"
                        cls._save_run_state(state)
                    
                    # 同时更新 state.json，将状态设为 stopped
                    try:
                        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
                        state_file = os.path.join(sim_dir, "state.json")
                        logger.info(f"尝试更新 state.json: {state_file}")
                        if os.path.exists(state_file):
                            with open(state_file, 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            state_data['status'] = 'stopped'
                            state_data['updated_at'] = datetime.now().isoformat()
                            # 原子写入
                            atomic_write_json(state_file, state_data)
                            logger.info(f"已更新 state.json 状态为 stopped: {simulation_id}")
                        else:
                            logger.warning(f"state.json 不存在: {state_file}")
                    except Exception as state_err:
                        logger.warning(f"更新 state.json 失败: {simulation_id}, error={state_err}")
                        
            except Exception as e:
                logger.error(f"清理进程失败: {simulation_id}, error={e}")
        
        # 清理文件句柄
        for simulation_id, file_handle in list(cls._stdout_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stdout_files.clear()
        
        for simulation_id, file_handle in list(cls._stderr_files.items()):
            try:
                if file_handle:
                    file_handle.close()
            except Exception:
                pass
        cls._stderr_files.clear()
        
        # 清理内存中的状态
        cls._processes.clear()
        cls._action_queues.clear()
        
        logger.info("模拟进程清理完成")
    
    @classmethod
    def register_cleanup(cls):
        """
        注册清理函数
        
        在 Flask 应用启动时调用，确保服务器关闭时清理所有模拟进程
        """
        global _cleanup_registered
        
        if _cleanup_registered:
            return
        
        # Flask debug 模式下，只在 reloader 子进程中注册清理（实际运行应用的进程）
        # WERKZEUG_RUN_MAIN=true 表示是 reloader 子进程
        # 如果不是 debug 模式，则没有这个环境变量，也需要注册
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        is_debug_mode = os.environ.get('FLASK_DEBUG') == '1' or os.environ.get('WERKZEUG_RUN_MAIN') is not None
        
        # 在 debug 模式下，只在 reloader 子进程中注册；非 debug 模式下始终注册
        if is_debug_mode and not is_reloader_process:
            _cleanup_registered = True  # 标记已注册，防止子进程再次尝试
            return
        
        # 保存原有的信号处理器
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        # SIGHUP 只在 Unix 系统存在（macOS/Linux），Windows 没有
        original_sighup = None
        has_sighup = hasattr(signal, 'SIGHUP')
        if has_sighup:
            original_sighup = signal.getsignal(signal.SIGHUP)
        
        def cleanup_handler(signum=None, frame=None):
            """信号处理器：先清理模拟进程，再调用原处理器"""
            # 只有在有进程需要清理时才打印日志
            if cls._processes or cls._graph_memory_enabled:
                logger.info(f"收到信号 {signum}，开始清理...")
            cls.cleanup_all_simulations()
            
            # 调用原有的信号处理器，让 Flask 正常退出
            if signum == signal.SIGINT and callable(original_sigint):
                original_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(original_sigterm):
                original_sigterm(signum, frame)
            elif has_sighup and signum == signal.SIGHUP:
                # SIGHUP: 终端关闭时发送
                if callable(original_sighup):
                    original_sighup(signum, frame)
                else:
                    # 默认行为：正常退出
                    sys.exit(0)
            else:
                # 如果原处理器不可调用（如 SIG_DFL），则使用默认行为
                raise KeyboardInterrupt
        
        # 注册 atexit 处理器（作为备用）
        atexit.register(cls.cleanup_all_simulations)
        
        # 注册信号处理器（仅在主线程中）
        try:
            # SIGTERM: kill 命令默认信号
            signal.signal(signal.SIGTERM, cleanup_handler)
            # SIGINT: Ctrl+C
            signal.signal(signal.SIGINT, cleanup_handler)
            # SIGHUP: 终端关闭（仅 Unix 系统）
            if has_sighup:
                signal.signal(signal.SIGHUP, cleanup_handler)
        except ValueError:
            # 不在主线程中，只能使用 atexit
            logger.warning("无法注册信号处理器（不在主线程），仅使用 atexit")
        
        _cleanup_registered = True
    
    @classmethod
    def get_running_simulations(cls) -> List[str]:
        """
        获取所有正在运行的模拟ID列表
        """
        running = []
        for sim_id, process in cls._processes.items():
            if process.poll() is None:
                running.append(sim_id)
        return running
    
    # ============== Interview 功能 ==============

    @classmethod
    def check_env_alive(cls, simulation_id: str) -> bool:
        """
        检查模拟环境是否存活（可以接收Interview命令）

        必修 9：除了 env_status.json 还要验证 _processes 中的实际进程
        原因：env_status.json 是心跳文件，子进程可能心跳后立即崩溃，
        但 status 文件还显示 alive，导致 IPC 必超时 504。

        Args:
            simulation_id: 模拟ID

        Returns:
            True 表示环境存活，False 表示环境已关闭
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return False

        ipc_client = SimulationIPCClient(sim_dir)
        # Step 1：先看 env_status.json（保留 8d35047 的快速判定）
        file_says_alive = ipc_client.check_env_alive()
        if not file_says_alive:
            return False

        # Step 2：必修 9 — 验证实际进程存活
        # _processes 是 SimulationRunner 维护的进程字典
        # 如果该 simulation_id 不在字典里，说明后端重启过 / 进程被外部清理
        process = cls._processes.get(simulation_id)
        if process is None:
            logger.warning(
                f"check_env_alive: env_status.json 说 alive 但 _processes 中没有 {simulation_id}，"
                f"判定 dead（可能后端重启后子进程未拉起）"
            )
            return False

        # 如果进程在字典里但已经退出（returncode != None），也算 dead
        if process.poll() is not None:
            logger.warning(
                f"check_env_alive: 子进程 PID={process.pid} 已退出 (returncode={process.returncode})，"
                f"env_status.json 仍显示 alive 但实际已 dead"
            )
            return False

        return True

    @classmethod
    def get_env_status_detail(cls, simulation_id: str) -> Dict[str, Any]:
        """
        获取模拟环境的详细状态信息

        Args:
            simulation_id: 模拟ID

        Returns:
            状态详情字典，包含 status, twitter_available, reddit_available, timestamp
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        status_file = os.path.join(sim_dir, "env_status.json")
        
        default_status = {
            "status": "stopped",
            "twitter_available": False,
            "reddit_available": False,
            "timestamp": None
        }
        
        if not os.path.exists(status_file):
            return default_status
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return {
                "status": status.get("status", "stopped"),
                "twitter_available": status.get("twitter_available", False),
                "reddit_available": status.get("reddit_available", False),
                "timestamp": status.get("timestamp")
            }
        except (json.JSONDecodeError, OSError):
            return default_status

    @classmethod
    def interview_agent(
        cls,
        simulation_id: str,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """
        采访单个Agent

        Args:
            simulation_id: 模拟ID
            agent_id: Agent ID
            prompt: 采访问题
            platform: 指定平台（可选）
                - "twitter": 只采访Twitter平台
                - "reddit": 只采访Reddit平台
                - None: 双平台模拟时同时采访两个平台，返回整合结果
            timeout: 超时时间（秒）

        Returns:
            采访结果字典

        Raises:
            ValueError: 模拟不存在或环境未运行
            TimeoutError: 等待响应超时
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"模拟不存在: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"模拟环境未运行或已关闭，无法执行Interview: {simulation_id}")

        logger.info(f"发送Interview命令: simulation_id={simulation_id}, agent_id={agent_id}, platform={platform}")

        response = ipc_client.send_interview(
            agent_id=agent_id,
            prompt=prompt,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "agent_id": agent_id,
                "prompt": prompt,
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "agent_id": agent_id,
                "prompt": prompt,
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_agents_batch(
        cls,
        simulation_id: str,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 30.0   # 修 #31:从 120s 降到 30s,auto-offline fallback 兜底(总等待 ≤30s)
    ) -> Dict[str, Any]:
        """
        批量采访多个Agent

        Args:
            simulation_id: 模拟ID
            interviews: 采访列表，每个元素包含 {"agent_id": int, "prompt": str, "platform": str(可选)}
            platform: 默认平台（可选，会被每个采访项的platform覆盖）
                - "twitter": 默认只采访Twitter平台
                - "reddit": 默认只采访Reddit平台
                - None: 双平台模拟时每个Agent同时采访两个平台
            timeout: 超时时间（秒）

        Returns:
            批量采访结果字典

        Raises:
            ValueError: 模拟不存在或环境未运行
            TimeoutError: 等待响应超时
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"模拟不存在: {simulation_id}")

        ipc_client = SimulationIPCClient(sim_dir)

        if not ipc_client.check_env_alive():
            raise ValueError(f"模拟环境未运行或已关闭，无法执行Interview: {simulation_id}")

        logger.info(f"发送批量Interview命令: simulation_id={simulation_id}, count={len(interviews)}, platform={platform}")

        response = ipc_client.send_batch_interview(
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )

        if response.status.value == "completed":
            return {
                "success": True,
                "interviews_count": len(interviews),
                "result": response.result,
                "timestamp": response.timestamp
            }
        else:
            return {
                "success": False,
                "interviews_count": len(interviews),
                "error": response.error,
                "timestamp": response.timestamp
            }
    
    @classmethod
    def interview_all_agents(
        cls,
        simulation_id: str,
        prompt: str,
        platform: str = None,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        采访所有Agent（全局采访）

        使用相同的问题采访模拟中的所有Agent

        Args:
            simulation_id: 模拟ID
            prompt: 采访问题（所有Agent使用相同问题）
            platform: 指定平台（可选）
                - "twitter": 只采访Twitter平台
                - "reddit": 只采访Reddit平台
                - None: 双平台模拟时每个Agent同时采访两个平台
            timeout: 超时时间（秒）

        Returns:
            全局采访结果字典
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"模拟不存在: {simulation_id}")

        # 从配置文件获取所有Agent信息
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.exists(config_path):
            raise ValueError(f"模拟配置不存在: {simulation_id}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_configs = config.get("agent_configs", [])
        if not agent_configs:
            raise ValueError(f"模拟配置中没有Agent: {simulation_id}")

        # 构建批量采访列表
        interviews = []
        for agent_config in agent_configs:
            agent_id = agent_config.get("agent_id")
            if agent_id is not None:
                interviews.append({
                    "agent_id": agent_id,
                    "prompt": prompt
                })

        logger.info(f"发送全局Interview命令: simulation_id={simulation_id}, agent_count={len(interviews)}, platform={platform}")

        return cls.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=interviews,
            platform=platform,
            timeout=timeout
        )
    
    @classmethod
    def close_simulation_env(
        cls,
        simulation_id: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        关闭模拟环境（而不是停止模拟进程）
        
        向模拟发送关闭环境命令，使其优雅退出等待命令模式
        
        Args:
            simulation_id: 模拟ID
            timeout: 超时时间（秒）
            
        Returns:
            操作结果字典
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            raise ValueError(f"模拟不存在: {simulation_id}")
        
        ipc_client = SimulationIPCClient(sim_dir)
        
        if not ipc_client.check_env_alive():
            return {
                "success": True,
                "message": "环境已经关闭"
            }
        
        logger.info(f"发送关闭环境命令: simulation_id={simulation_id}")
        
        try:
            response = ipc_client.send_close_env(timeout=timeout)
            
            return {
                "success": response.status.value == "completed",
                "message": "环境关闭命令已发送",
                "result": response.result,
                "timestamp": response.timestamp
            }
        except TimeoutError:
            # 超时可能是因为环境正在关闭
            return {
                "success": True,
                "message": "环境关闭命令已发送（等待响应超时，环境可能正在关闭）"
            }
    
    @classmethod
    def _get_interview_history_from_db(
        cls,
        db_path: str,
        platform_name: str,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """从单个数据库获取Interview历史"""
        import sqlite3
        
        if not os.path.exists(db_path):
            return []
        
        results = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if agent_id is not None:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview' AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (agent_id, limit))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = 'interview'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            for user_id, info_json, created_at in cursor.fetchall():
                try:
                    info = json.loads(info_json) if info_json else {}
                except json.JSONDecodeError:
                    info = {"raw": info_json}
                
                results.append({
                    "agent_id": user_id,
                    "response": info.get("response", info),
                    "prompt": info.get("prompt", ""),
                    "timestamp": created_at,
                    "platform": platform_name
                })
            
            conn.close()
            
        except Exception as e:
            logger.error(f"读取Interview历史失败 ({platform_name}): {e}")
        
        return results

    @classmethod
    def get_interview_history(
        cls,
        simulation_id: str,
        platform: str = None,
        agent_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取Interview历史记录（从数据库读取）
        
        Args:
            simulation_id: 模拟ID
            platform: 平台类型（reddit/twitter/None）
                - "reddit": 只获取Reddit平台的历史
                - "twitter": 只获取Twitter平台的历史
                - None: 获取两个平台的所有历史
            agent_id: 指定Agent ID（可选，只获取该Agent的历史）
            limit: 每个平台返回数量限制
            
        Returns:
            Interview历史记录列表
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        
        results = []
        
        # 确定要查询的平台
        if platform in ("reddit", "twitter"):
            platforms = [platform]
        else:
            # 不指定platform时，查询两个平台
            platforms = ["twitter", "reddit"]
        
        for p in platforms:
            db_path = os.path.join(sim_dir, f"{p}_simulation.db")
            platform_results = cls._get_interview_history_from_db(
                db_path=db_path,
                platform_name=p,
                agent_id=agent_id,
                limit=limit
            )
            results.extend(platform_results)
        
        # 按时间降序排序
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # 如果查询了多个平台，限制总数
        if len(platforms) > 1 and len(results) > limit:
            results = results[:limit]

        return results

    # ==================== 快照功能 ====================

    @classmethod
    def _validate_snapshot_name(cls, snapshot_name: str) -> Optional[str]:
        """
        关键修复（RISK-2/6）：sanitize + 校验 snapshot_name
        拒绝路径分隔符、NUL、.、..，并截断到 200 字符内。
        返回 sanitize 后的名字（None 表示拒绝、调用方应返回 400）。
        """
        if not isinstance(snapshot_name, str):
            return None
        s = snapshot_name.strip()
        if not s or s in (".", ".."):
            return None
        if '/' in s or '\\' in s or '\x00' in s:
            return None
        if len(s) > 200:
            s = s[:200]
        return s

    @classmethod
    def create_snapshot(cls, simulation_id: str, snapshot_name: Optional[str] = None) -> Dict[str, Any]:
        """
        创建模拟快照（完整保存当前运行状态）

        快照包含：
        - run_state.json — 运行状态（轮次、进度、动作等）
        - simulation_config.json — 模拟配置（Agent 配置、时代变量等）
        - reddit/actions.jsonl / twitter/actions.jsonl — 所有动作记录
        - reddit_simulation.db / twitter_simulation.db — 模拟数据库
        - 图谱文件（如果存在）

        Args:
            simulation_id: 模拟ID
            snapshot_name: 快照名称（可选，默认使用时间戳）

        Returns:
            快照信息（路径、名称、时间戳等）
        """
        import shutil
        from datetime import datetime

        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return {
                "success": False,
                "error": f"模拟目录不存在: {simulation_id}"
            }

        # 生成快照名称
        if snapshot_name:
            snapshot_name = cls._validate_snapshot_name(snapshot_name)
            if snapshot_name is None:
                return {
                    "success": False,
                    "error": "快照名称不合法（包含路径分隔符或为 . / ..）"
                }
        else:
            snapshot_name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        snapshot_dir = os.path.join(sim_dir, "snapshots", snapshot_name)

        # 如果快照目录已存在，删除后重建
        if os.path.exists(snapshot_dir):
            shutil.rmtree(snapshot_dir)

        # 创建快照目录
        os.makedirs(snapshot_dir, exist_ok=True)

        # 文件清单：需要保存的关键文件
        files_to_snapshot = [
            "run_state.json",
            "simulation_config.json",
            "state.json",
        ]

        # 平台目录：actions.jsonl
        dirs_to_snapshot = ["reddit", "twitter"]

        snapshot_files = []
        errors = []

        # 保存文件
        for filename in files_to_snapshot:
            src = os.path.join(sim_dir, filename)
            if os.path.exists(src):
                dst = os.path.join(snapshot_dir, filename)
                try:
                    shutil.copy2(src, dst)
                    snapshot_files.append(filename)
                except Exception as e:
                    errors.append(f"复制 {filename} 失败: {str(e)}")

        # 保存平台目录
        for dir_name in dirs_to_snapshot:
            src_dir = os.path.join(sim_dir, dir_name)
            if os.path.exists(src_dir):
                dst_dir = os.path.join(snapshot_dir, dir_name)
                try:
                    # 只复制 actions.jsonl 和 profiles.json
                    for file_in_dir in ["actions.jsonl", "profiles.json"]:
                        src_file = os.path.join(src_dir, file_in_dir)
                        if os.path.exists(src_file):
                            dst_file = os.path.join(dst_dir, file_in_dir)
                            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                            shutil.copy2(src_file, dst_file)
                            snapshot_files.append(f"{dir_name}/{file_in_dir}")
                except Exception as e:
                    errors.append(f"复制 {dir_name} 目录失败: {str(e)}")

        # 保存数据库文件
        # 修复（活跃 DB 撕裂拷贝）：周期自动快照/手动快照可能在子进程持续写库时执行。
        # shutil.copy2 直接拷主 DB 文件不拷 -journal → 事务提交中途拷贝时主库已含
        # 未提交页，恢复后 SQLite 将其视为已提交 → 静默数据损坏，resume 状态错乱。
        # 修复方式：.db 文件改用 sqlite3 在线 backup API，得到事务边界上一致完整的副本；
        # backup 内部遇写锁竞争自动重试（sleep=0.25s），与写入方自然共存。
        # backup 失败（如文件非 SQLite）回退 copy2 并 warning（至少等同旧行为）。
        def _backup_sqlite_db(src_path: str, dst_path: str) -> None:
            import sqlite3
            src_conn = sqlite3.connect(src_path)
            try:
                dst_conn = sqlite3.connect(dst_path)
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()
            finally:
                src_conn.close()

        db_files = [
            "reddit_simulation.db",
            "reddit_simulation_*.db",
            "twitter_simulation.db",
            "twitter_simulation_*.db",
        ]

        import glob
        for db_pattern in db_files:
            matching_files = glob.glob(os.path.join(sim_dir, db_pattern))
            for db_path in matching_files:
                db_name = os.path.basename(db_path)
                dst = os.path.join(snapshot_dir, db_name)
                try:
                    if db_name.endswith(".db"):
                        try:
                            _backup_sqlite_db(db_path, dst)
                        except Exception as backup_err:
                            logger.warning(
                                f"SQLite backup 失败 {db_name}: {backup_err}，回退直接拷贝"
                                f"（注意：DB 可能正在写入，快照一致性不保证）"
                            )
                            shutil.copy2(db_path, dst)
                    else:
                        shutil.copy2(db_path, dst)
                    snapshot_files.append(db_name)
                except Exception as e:
                    errors.append(f"复制 {db_name} 失败: {str(e)}")

        # 保存 agent memory + Python/OASIS random state + runtime state 目录。
        # 这些目录由子脚本每轮落盘,snapshot 必须一并复制,才能保证
        # 恢复时 resume 流程可以从历史 memory + random state 接续
        # (而不仅仅依赖 DB)。
        runtime_dirs_to_snapshot = [
            "agent_memory",
            "random_state",
            "runtime_state",
        ]
        for subdir in runtime_dirs_to_snapshot:
            src_dir = os.path.join(sim_dir, subdir)
            if not os.path.isdir(src_dir):
                continue
            dst_dir = os.path.join(snapshot_dir, subdir)
            try:
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
                for root, _, files in os.walk(dst_dir):
                    for fname in files:
                        rel = os.path.relpath(os.path.join(root, fname), snapshot_dir)
                        rel = rel.replace(os.sep, "/")
                        snapshot_files.append(rel)
            except Exception as e:
                errors.append(f"复制 {subdir} 目录失败: {str(e)}")

        # 保存快照元数据
        metadata = {
            "snapshot_name": snapshot_name,
            "snapshot_dir": snapshot_dir,
            "simulation_id": simulation_id,
            "created_at": datetime.now().isoformat(),
            "files": snapshot_files,
            "run_state": None,
        }

        # 加载运行状态
        run_state = cls.get_run_state(simulation_id)
        if run_state:
            metadata["run_state"] = run_state.to_dict()

        # 记录快照时的当前轮次、总轮次和原始 max_rounds（用于恢复时从快照继续）
        # total_rounds 代表整个模拟的总轮数（可能已被原 max_rounds 截断），不是剩余轮数，必须保存
        # user_max_rounds 是用户原始传入的目标最大轮数（0 表示未设置），必须保存以便恢复时知道原始意图
        if metadata["run_state"]:
            metadata["current_round"] = metadata["run_state"].get("current_round", 0)
            metadata["total_rounds"] = metadata["run_state"].get("total_rounds", 0)
            metadata["user_max_rounds"] = metadata["run_state"].get("user_max_rounds", 0)
        else:
            metadata["current_round"] = 0
            metadata["total_rounds"] = 0
            metadata["user_max_rounds"] = 0

        metadata_path = os.path.join(snapshot_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {
            "success": len(errors) == 0,
            "snapshot_name": snapshot_name,
            "snapshot_dir": snapshot_dir,
            "simulation_id": simulation_id,
            "files": snapshot_files,
            "errors": errors if errors else None,
            "run_state": metadata["run_state"],
        }

    @classmethod
    def _cleanup_old_auto_snapshots(cls, simulation_id: str) -> int:
        """
        优化 S1：仅清理周期性 / 崩溃自动快照，保留最近 K 个；手动快照永不清理。

        命名约定：
        - auto snapshot: auto_r<round>_<timestamp>  ← 自动清理
        - crash snapshot: crash_r<round>_<timestamp>  ← 自动清理
        - 其它（用户手动）: 保留

        Args:
            simulation_id: 模拟ID

        Returns:
            实际删除的快照数量
        """
        import shutil
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        snapshots_dir = os.path.join(sim_dir, "snapshots")
        if not os.path.exists(snapshots_dir):
            return 0

        keep = Config.SIMULATION_AUTO_SNAPSHOTS_KEEP
        # 收集所有 auto/crash 快照（按目录 mtime 降序 = 最新在前）
        auto_snaps = []
        for name in os.listdir(snapshots_dir):
            full = os.path.join(snapshots_dir, name)
            if not os.path.isdir(full):
                continue
            if name.startswith("auto_") or name.startswith("crash_"):
                auto_snaps.append((os.path.getmtime(full), name, full))

        auto_snaps.sort(reverse=True)  # 最新在前

        deleted = 0
        for i, (_, name, full) in enumerate(auto_snaps):
            if i < keep:
                continue  # 保留前 K 个
            try:
                shutil.rmtree(full)
                deleted += 1
                logger.debug(f"清理旧 auto snapshot: {name}")
            except Exception as e:
                logger.warning(f"清理快照失败 {name}: {e}")

        if deleted > 0:
            logger.info(f"清理 {deleted} 个旧 auto snapshot（保留最近 {keep} 个）")
        return deleted

    @classmethod
    def list_snapshots(cls, simulation_id: str) -> Dict[str, Any]:
        """
        列出模拟的所有快照

        Args:
            simulation_id: 模拟ID

        Returns:
            快照列表
        """
        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        snapshots_dir = os.path.join(sim_dir, "snapshots")

        if not os.path.exists(snapshots_dir):
            return {
                "success": True,
                "snapshots": []
            }

        snapshots = []
        for snapshot_name in sorted(os.listdir(snapshots_dir)):
            snapshot_dir = os.path.join(snapshots_dir, snapshot_name)
            if not os.path.isdir(snapshot_dir):
                continue

            metadata_path = os.path.join(snapshot_dir, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    # 平台真实轮次（runtime_state 由子进程每轮结束原子写入，比
                    # run_state 的 monitor 5s 落盘更准）：前端恢复弹窗据此显示各平台
                    # 续跑轮次/完成状态，避免 run_state 滞后导致显示偏差
                    for _platform in ("twitter", "reddit"):
                        _rt_path = os.path.join(snapshot_dir, "runtime_state", f"{_platform}.json")
                        try:
                            if os.path.exists(_rt_path):
                                with open(_rt_path, 'r', encoding='utf-8') as _f:
                                    _rt = json.load(_f)
                                _completed = _rt.get("completed_round")
                                if isinstance(_completed, int) and _completed >= 0:
                                    metadata.setdefault("runtime_rounds", {})[_platform] = _completed
                        except (OSError, json.JSONDecodeError):
                            pass
                    snapshots.append(metadata)
                except Exception as e:
                    logger.error(f"读取快照元数据失败: {snapshot_name}, error: {e}")

        # 关键修复：按 created_at 时间倒序（最新在前），避免字典序错位
        # 旧实现使用 sorted(os.listdir(...)) 字典序，auto_r10_xxx < auto_r3_xxx，
        # 导致 /health 的 latest_snapshot_name 实际指向较旧快照。
        def _snap_sort_key(s: dict):
            # 容错：created_at 缺失/解析失败时回退到 0，不会让整个列表崩溃
            try:
                from datetime import datetime as _dt
                return _dt.fromisoformat(s.get("created_at", "")).timestamp()
            except Exception:
                return 0.0
        snapshots.sort(key=_snap_sort_key, reverse=True)

        return {
            "success": True,
            "snapshots": snapshots
        }

    @classmethod
    def restore_snapshot(cls, simulation_id: str, snapshot_name: str) -> Dict[str, Any]:
        """
        恢复模拟快照

        从快照恢复完整的模拟状态：
        - 恢复 run_state.json（运行状态）
        - 恢复 simulation_config.json（模拟配置）
        - 恢复 actions.jsonl（动作记录）
        - 恢复数据库文件

        Args:
            simulation_id: 模拟ID
            snapshot_name: 快照名称

        Returns:
            恢复结果
        """
        import shutil

        # 关键修复（RISK-6）：在 runner 层兜底校验 snapshot_name
        # 即使 API 层被绕过，也禁止路径分隔符 / NUL / . / ..
        snapshot_name = cls._validate_snapshot_name(snapshot_name) if snapshot_name else None
        if not snapshot_name:
            return {
                "success": False,
                "error": "快照名称不合法"
            }

        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        snapshot_dir = os.path.join(sim_dir, "snapshots", snapshot_name)

        if not os.path.exists(snapshot_dir):
            return {
                "success": False,
                "error": f"快照目录不存在: {snapshot_name}"
            }

        # 读取快照元数据
        metadata_path = os.path.join(snapshot_dir, "metadata.json")
        if not os.path.exists(metadata_path):
            return {
                "success": False,
                "error": "快照元数据不存在"
            }

        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        restored_files = []
        errors = []

        # 自检修复：恢复快照前先清理旧的子进程/监控线程
        # （快照恢复典型路径：用户已停止模拟或希望从头开始。如果有旧进程未清理，
        # 恢复后再启动会导致双进程并发写文件）
        cls._cleanup_stale_simulation_resources(
            simulation_id,
            reason=f"恢复快照前清理: {snapshot_name}"
        )

        # 恢复文件到模拟目录
        for filename in metadata.get("files", []):
            src = os.path.join(snapshot_dir, filename)
            dst = os.path.join(sim_dir, filename)

            # 创建目标目录（如果需要）
            os.makedirs(os.path.dirname(dst), exist_ok=True)

            try:
                shutil.copy2(src, dst)
                restored_files.append(filename)
            except Exception as e:
                errors.append(f"恢复 {filename} 失败: {str(e)}")

        # 关键修复（BUG-7/8）：恢复快照后清理 IPC 命令/响应残留
        # 避免旧命令被新子进程误处理
        cls._cleanup_ipc_dirs(simulation_id)

        # 自检修复：清理 actions.jsonl 中残留的 simulation_end 事件
        # 原因：如果快照是从 COMPLETE 状态创建的，actions.jsonl 末尾会有 simulation_end 标记。
        # 恢复后监控线程从位置 0 开始读，会先看到旧的 simulation_end 并设置 runner_status=COMPLETED，
        # 导致新进程还没跑就被前端误判为已完成。
        # 处理：找到每个平台 actions.jsonl 中最后一个 simulation_end，截掉它及其之后的所有内容。
        # 这样旧的历史保留（前端仍能看到），但干扰新进程的 simulation_end 标记被清掉。
        for platform in ("twitter", "reddit"):
            actions_file = os.path.join(sim_dir, platform, "actions.jsonl")
            if not os.path.exists(actions_file):
                continue
            try:
                with open(actions_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 找到最后一个 simulation_end 的行号
                cut_index = len(lines)
                for i in range(len(lines) - 1, -1, -1):
                    try:
                        data = json.loads(lines[i].strip())
                        if data.get("event_type") == "simulation_end":
                            cut_index = i
                            break
                    except (json.JSONDecodeError, ValueError):
                        continue
                if cut_index < len(lines):
                    removed = len(lines) - cut_index
                    with open(actions_file, 'w', encoding='utf-8') as f:
                        f.writelines(lines[:cut_index])
                    logger.info(
                        f"清理 {platform}/actions.jsonl 末尾的 {removed} 行（含 simulation_end），"
                        f"避免新进程启动时被旧标记干扰"
                    )
            except Exception as e:
                logger.warning(f"清理 {platform}/actions.jsonl 失败: {e}")

        # 历史 actions 保留（不再物理清空）：
        # 之前为了解决"恢复后误以为从 R0 开始"把 actions.jsonl 的旧动作全删了，
        # 副作用是恢复后前端时间轴只剩最后一轮的几个动作，历史全部丢失，
        # 用户无法回顾 R0~R(n-1) 的完整模拟过程。
        # 现在防重复靠三层（均已保留）：
        #   1. position 重置到文件末尾 → monitor 不重复读旧 actions
        #   2. recent_actions 清空 → "最近动作"只显示恢复后的新动作
        #   3. simulation_end 截断（上面的循环）→ 旧结束标记不干扰新进程
        # 前端 all_actions 全量读 actions.jsonl → 恢复后能看到 R0~R(n-1) 历史 + 新 actions。

        # 恢复 agent memory + Python/OASIS random state + runtime state 目录
        # (snapshots/<name>/ 下已 copy 过来),覆盖 fresh 模式运行时可能残留的旧状态。
        # 子脚本在 resume 流程会读这些目录恢复 agent memory 与 random state。
        for subdir in ("agent_memory", "random_state", "runtime_state"):
            src_dir = os.path.join(snapshot_dir, subdir)
            if not os.path.isdir(src_dir):
                continue
            dst_dir = os.path.join(sim_dir, subdir)
            try:
                if os.path.exists(dst_dir):
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                logger.info(f"恢复 {subdir}/ 目录(用于 resume 加载 agent memory / random state)")
            except Exception as e:
                logger.warning(f"恢复 {subdir}/ 目录失败: {e}")

        # 修正 run_state.json 中的 runner_status（必须是 idle，因为模拟需要重新启动）
        run_state_file = os.path.join(sim_dir, "run_state.json")
        if os.path.exists(run_state_file):
            try:
                with open(run_state_file, 'r', encoding='utf-8') as f:
                    run_state_data = json.load(f)
                # 重置 runner_status 为 idle
                run_state_data["runner_status"] = "idle"
                # 如果 start_round > 0，保留 current_round；否则重置为 0
                # 注意：start_round 参数由前端传递，这里检查 metadata 中的值
                current_round = metadata.get("current_round", 0)
                total_rounds = metadata.get("total_rounds", 0)
                # 修复：恢复快照后，current_round 应该是快照时的轮次，runner_status 必须是 idle
                # 同时必须保留 total_rounds，这是整个模拟的总轮数，不是剩余轮数
                run_state_data["current_round"] = current_round
                # 快照恢复时，优先使用快照中的 total_rounds 值
                # 因为 total_rounds 代表整个模拟的总轮数，应该以快照时为准
                if total_rounds > 0:
                    run_state_data["total_rounds"] = total_rounds
                    logger.info(f"从快照恢复 total_rounds: {total_rounds}")
                # 【快照恢复标记】
                # 写入 restored_at 时间戳，作为 _start_simulation_impl 判断"快照恢复场景"
                # 的可靠信号。
                # 旧实现仅依赖 runner_status == 'idle'，在崩溃/异常路径下不可靠
                # （残留的 running/stopping 状态会让 restored_from_snapshot 判 False，
                #  导致 --max-rounds 不透传，子脚本按 time_config 重算 total_rounds 多跑数轮）。
                run_state_data["restored_at"] = datetime.now().isoformat()
                run_state_data["restored_snapshot_name"] = snapshot_name
                # 修复（快照恢复重复读取 R0~R4 actions bug）：
                # restore_snapshot 把 actions.jsonl 替换为快照里的旧数据，
                # 但 run_state.json 里的 twitter_actions_log_position / reddit_actions_log_position
                # 仍是上一次运行时的旧值（可能大于新文件大小）。
                # 必须在恢复后把 position 设回当前文件大小（"已读到当前文件末尾"），
                # 避免 monitor 启动时按旧 position seek 错位 → 重读 R0~R4 旧 actions。
                for platform, key in (("twitter", "twitter_actions_log_position"),
                                      ("reddit",  "reddit_actions_log_position")):
                    actions_file = os.path.join(sim_dir, platform, "actions.jsonl")
                    if os.path.exists(actions_file):
                        try:
                            file_size = os.path.getsize(actions_file)
                            run_state_data[key] = file_size
                            logger.info(f"快照恢复后 {key} 重置为文件大小 {file_size}")
                        except OSError:
                            pass
                # 修复（恢复后 A: 计数与文件不一致）：
                # create_snapshot 直接拷贝磁盘上的 run_state.json，而 monitor 每 5s
                # 才落盘一次 → 快照里的 twitter/reddit_actions_count 最多滞后 5s，
                # 比快照 actions.jsonl 的实际条数少几个。恢复后 A: 从这个滞后基数
                # 开始累加，永远比真实总数偏小。
                # 修复方式：恢复时从恢复后的 actions.jsonl 重新精确计数
                # （与 _read_actions_from_file 同口径：跳过 event_type 行、要求有 agent_id），
                # 使 A: 基数与文件内容严格一致。
                for platform, count_key in (("twitter", "twitter_actions_count"),
                                            ("reddit",  "reddit_actions_count")):
                    actions_file = os.path.join(sim_dir, platform, "actions.jsonl")
                    if not os.path.exists(actions_file):
                        continue
                    exact_count = 0
                    try:
                        with open(actions_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    data = json.loads(line)
                                except (json.JSONDecodeError, ValueError):
                                    continue
                                if "event_type" in data or "agent_id" not in data:
                                    continue
                                exact_count += 1
                        old_count = run_state_data.get(count_key)
                        if old_count != exact_count:
                            logger.info(
                                f"快照恢复后 {count_key} 按文件重新计数: "
                                f"{old_count} -> {exact_count}（快照内 run_state 可能滞后于 actions.jsonl）"
                            )
                        run_state_data[count_key] = exact_count
                    except OSError as e:
                        logger.warning(f"恢复时重新计数 {count_key} 失败(沿用快照值): {e}")
                # 同源修复（T: 模拟时长滞后）：round_end 事件携带 simulated_hours，
                # 快照内 run_state 若滞后就少算最后一轮。顺序扫描找各平台最后一个
                # round_end 的 simulated_hours，与计数保持同等的精确性。
                _restored_platform_hours = {}
                for platform, hour_key in (("twitter", "twitter_simulated_hours"),
                                           ("reddit",  "reddit_simulated_hours")):
                    actions_file = os.path.join(sim_dir, platform, "actions.jsonl")
                    if not os.path.exists(actions_file):
                        continue
                    try:
                        last_hours = None
                        with open(actions_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    data = json.loads(line)
                                except (json.JSONDecodeError, ValueError):
                                    continue
                                if data.get("event_type") == "round_end" and "simulated_hours" in data:
                                    last_hours = data.get("simulated_hours", 0)
                        if last_hours is not None:
                            old_hours = run_state_data.get(hour_key)
                            if old_hours != last_hours:
                                logger.info(
                                    f"快照恢复后 {hour_key} 按文件修正: {old_hours} -> {last_hours}"
                                )
                            run_state_data[hour_key] = last_hours
                            _restored_platform_hours[platform] = last_hours
                    except OSError as e:
                        logger.warning(f"恢复时修正 {hour_key} 失败(沿用快照值): {e}")
                # 总时长 = 两平台最大值（与 monitor 的 max 语义一致）
                if _restored_platform_hours:
                    run_state_data["simulated_hours"] = max(_restored_platform_hours.values())
                # 修复（恢复后平台轮次显示错误/误导）：
                # run_state.json 中的 twitter_current_round / reddit_current_round
                # 来自 monitor 每 5s 的落盘，可能滞后于子进程 runtime_state 中
                # 的真实 completed_round（例如快照保存瞬间 monitor 还没读到最后一轮
                # round_end）。恢复后 UI 以此为显示基数，滞后值会让轮次显示落后一拍。
                # 修复：恢复时用 runtime_state/<platform>.json 的 completed_round
                # 覆盖（该文件由子进程每轮结束原子写入，是平台真实进度）。
                _restored_platform_rounds = {}
                for platform, round_key in (("twitter", "twitter_current_round"),
                                            ("reddit",  "reddit_current_round")):
                    runtime_path = os.path.join(sim_dir, "runtime_state", f"{platform}.json")
                    if not os.path.exists(runtime_path):
                        continue
                    try:
                        with open(runtime_path, 'r', encoding='utf-8') as f:
                            runtime_data = json.load(f)
                        completed = runtime_data.get("completed_round")
                        if isinstance(completed, int) and completed >= 0:
                            old_round = run_state_data.get(round_key)
                            if old_round != completed:
                                logger.info(
                                    f"快照恢复后 {round_key} 按平台真实进度修正: "
                                    f"{old_round} -> {completed}（run_state 可能滞后于 runtime_state）"
                                )
                            run_state_data[round_key] = completed
                            _restored_platform_rounds[platform] = completed
                    except (OSError, json.JSONDecodeError) as e:
                        logger.warning(f"恢复时读取 {platform} runtime_state 失败(沿用快照值): {e}")
                # 总轮次对齐：与 monitor 的 max 语义一致，避免 current_round 落后于平台轮次
                if _restored_platform_rounds:
                    run_state_data["current_round"] = max(
                        run_state_data.get("current_round", 0) or 0,
                        max(_restored_platform_rounds.values()),
                    )
                # 修复（快照恢复 recent_actions 残留 bug）：
                # 快照里的 recent_actions 字段是上次模拟的最近 50 条 actions（包含 R0~R2）。
                # restore_snapshot 把这个数组拷到 sim_dir/run_state.json 后，
                # 前端轮询 /run-status/detail 时会从 disk 读 recent_actions，显示 R0~R2 actions → 用户误以为"从 R0 开始"。
                # 必须在恢复时清空 recent_actions，强制 monitor 从 actions.jsonl 当前 position
                # 重新同步（position 字段已设到 file_size，跳过旧数据）。
                run_state_data["recent_actions"] = []
                # 原子写入：避免快照恢复过程中前端读到半截 JSON
                atomic_write_json(run_state_file, run_state_data)
                logger.info(
                    f"修正 run_state.json: runner_status -> idle, current_round -> {current_round}, "
                    f"total_rounds -> {run_state_data.get('total_rounds', 'unchanged')}, "
                    f"restored_at -> {run_state_data['restored_at']}"
                )
            except Exception as e:
                logger.warning(f"修正 run_state.json 失败: {e}")

        # 清除内存中的运行状态（确保下次查询时从文件重新加载）
        # 注意：进程/线程/文件句柄的清理已在函数开头通过 _cleanup_stale_simulation_resources 完成
        if simulation_id in cls._run_states:
            del cls._run_states[simulation_id]

        logger.info(
            "恢复快照完成: %s/%s, 恢复文件: %d, 快照轮次: %s",
            simulation_id,
            snapshot_name,
            len(restored_files),
            metadata.get("current_round", 0),
        )

        # 同步 SimulationManager 的 state.json 状态
        # 注意：恢复快照后，状态应设置为 READY，因为模拟需要重新启动
        try:
            from .simulation_manager import SimulationManager, SimulationStatus
            manager = SimulationManager()
            sim_state = manager.get_simulation(simulation_id)
            if sim_state:
                # 恢复快照后模拟状态应为 READY，等待用户启动
                sim_state.status = SimulationStatus.READY
                sim_state.current_round = metadata.get("current_round", 0)
                manager._save_simulation_state(sim_state)
                logger.info(f"恢复快照后已同步 state.json: {simulation_id} -> {SimulationStatus.READY.value}")
        except Exception as e:
            logger.warning(f"恢复快照后同步 state.json 失败: {simulation_id}, error={e}")

        # 返回值补充平台独立轮次（前端恢复日志显示"Plaza R4 / Community R3"，
        # 而非单一 current_round+1，避免双平台轮次不一致时误导）。
        # 优先读恢复后（已按 runtime_state 修正过的）run_state.json。
        _return_tw_round = None
        _return_rd_round = None
        try:
            with open(os.path.join(sim_dir, "run_state.json"), 'r', encoding='utf-8') as f:
                _post_restore_state = json.load(f)
            _return_tw_round = _post_restore_state.get("twitter_current_round")
            _return_rd_round = _post_restore_state.get("reddit_current_round")
        except (OSError, json.JSONDecodeError):
            pass

        return {
            "success": len(errors) == 0,
            "snapshot_name": snapshot_name,
            "simulation_id": simulation_id,
            "restored_files": restored_files,
            "errors": errors if errors else None,
            "current_round": metadata.get("current_round", 0),
            "total_rounds": metadata.get("total_rounds", 0),
            "twitter_round": _return_tw_round,
            "reddit_round": _return_rd_round,
        }

    @classmethod
    def delete_snapshot(cls, simulation_id: str, snapshot_name: str) -> Dict[str, Any]:
        """
        删除指定快照

        Args:
            simulation_id: 模拟ID
            snapshot_name: 快照名称

        Returns:
            删除结果
        """
        import shutil

        # 关键修复（RISK-6）：runner 层兜底校验
        snapshot_name = cls._validate_snapshot_name(snapshot_name) if snapshot_name else None
        if not snapshot_name:
            return {
                "success": False,
                "error": "快照名称不合法"
            }

        sim_dir = os.path.join(cls.RUN_STATE_DIR, simulation_id)
        snapshot_dir = os.path.join(sim_dir, "snapshots", snapshot_name)

        if not os.path.exists(snapshot_dir):
            return {
                "success": False,
                "error": f"快照不存在: {snapshot_name}"
            }

        try:
            shutil.rmtree(snapshot_dir)
            logger.info(f"删除快照完成: {simulation_id}/{snapshot_name}")
            return {
                "success": True,
                "snapshot_name": snapshot_name,
            }
        except Exception as e:
            logger.error(f"删除快照失败: {simulation_id}/{snapshot_name}, error: {e}")
            return {
                "success": False,
                "error": f"删除失败: {str(e)}"
            }


