"""
Agent Persona 缓存管理器

将 OASIS 的 agent_graph 持久化到磁盘,以避免每次启动子进程时
重新构造 320 个 SocialAgent(~50s)。

设计原则:
- 只存 persona 数据(UserInfo + available_actions),不 pickle 整个 SocialAgent
  (SocialAgent 含 Channel/ModelManager/Memory 等不可 pickle 字段)
- JSON 格式可读、可追查、跨版本兼容
- sha256 指纹校验:profile 或 simulation_config 变动自动失效
- 仿 Redis 经典清理:TTL + 单 sim max-count
"""

import os
import json
import hashlib
import logging
import shutil
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional

from ..config import Config


logger = logging.getLogger('mirofish.agent_cache_manager')


class CachePlatform(str, Enum):
    """被缓存的平台。统一小写,跟 file 命名一致。"""
    TWITTER = "twitter"
    REDDIT = "reddit"


class AgentCacheManager:
    """
    Agent persona 持久化。

    缓存文件位置: `{simulation_dir}/agent_cache/{platform}_v{schema_version}.json`

    Schema v1: JSON 顶层 {schema_version, platform, created_at, profile_sha256, config_sha256, agents}
    每个 agent: {agent_id, user_info: {...raw dataclass dict...}, available_actions: [str, str, ...]}
    """

    CACHE_DIR_NAME = "agent_cache"
    SCHEMA_VERSION = 1

    # ============= 路径辅助 =============

    @classmethod
    def get_cache_dir(cls, sim_dir: str) -> str:
        """sim_dir 下的 agent_cache 子目录绝对路径。"""
        return os.path.join(sim_dir, cls.CACHE_DIR_NAME)

    @classmethod
    def get_cache_path(cls, sim_dir: str, platform: CachePlatform) -> str:
        """单平台 cache 文件绝对路径。"""
        return os.path.join(
            cls.get_cache_dir(sim_dir),
            f"{platform.value}_v{cls.SCHEMA_VERSION}.json"
        )

    # ============= 哈希 =============

    @classmethod
    def sha256_file(cls, file_path: str) -> Optional[str]:
        """算文件 sha256。文件不存在或读不动 → None。"""
        if not os.path.isfile(file_path):
            return None
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as e:
            logger.warning(f"sha256_file 失败 {file_path}: {e}")
            return None

    # ============= 核心读写 =============

    @classmethod
    def save_cache(
        cls,
        sim_dir: str,
        platform: CachePlatform,
        agents: List[Any],
        profile_path: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> bool:
        """
        保存 agent_graph 的 persona 数据。

        Args:
            sim_dir: 模拟目录绝对路径
            platform: CachePlatform.TWITTER / REDDIT
            agents: List[SocialAgent] 或 List[dict];每个对象要么是 SocialAgent (取 user_info / action_tools)
                   要么是 dict (取 agent_id / user_info / available_actions / action_tools)
            profile_path: 关联的 profile 文件路径(用于指纹计算)
            config_path: 关联的 simulation_config.json 路径(用于指纹计算)

        Returns:
            True=成功写盘;False=写入失败(失败原因已 log)
        """
        if not Config.AGENT_CACHE_ENABLED:
            return False

        cache_path = cls.get_cache_path(sim_dir, platform)
        cache_dir = cls.get_cache_dir(sim_dir)

        # 提取 agent dict —— 兼容两种输入
        agent_dicts: List[Dict[str, Any]] = []
        for agent in agents:
            try:
                if isinstance(agent, dict):
                    user_info = agent.get("user_info")
                    available_actions = agent.get("available_actions") or agent.get("action_tools")
                    agent_id = agent.get("agent_id")
                else:
                    # SocialAgent 实例
                    user_info = getattr(agent, "user_info", None)
                    action_tools = getattr(agent, "action_tools", None)
                    available_actions = action_tools  # list of ActionType members
                    agent_id = getattr(agent, "social_agent_id", None)

                if user_info is None or agent_id is None:
                    continue

                # 把 UserInfo dataclass -> dict,available_actions ActionType -> str
                ui_dict = cls._serialize_user_info(user_info)
                actions_str = cls._serialize_actions(available_actions)

                agent_dicts.append({
                    "agent_id": int(agent_id),
                    "user_info": ui_dict,
                    "available_actions": actions_str,
                })
            except Exception as e:
                logger.warning(f"序列化 agent 失败(已跳过): {e}")
                continue

        if not agent_dicts:
            logger.warning(f"save_cache: 没有任何合法 agent 可写({platform.value}),skip")
            return False

        # 计算 sha256(可选)
        profile_sha256 = cls.sha256_file(profile_path) if profile_path else ""
        config_sha256 = cls.sha256_file(config_path) if config_path else ""

        payload = {
            "schema_version": cls.SCHEMA_VERSION,
            "platform": platform.value,
            "created_at": datetime.now().isoformat(),
            "profile_sha256": profile_sha256,
            "config_sha256": config_sha256,
            "agent_count": len(agent_dicts),
            "agents": agent_dicts,
        }

        try:
            os.makedirs(cache_dir, exist_ok=True)
            # 写临时文件 + 原子改名,避免写到一半被打断
            tmp_path = cache_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=None, default=str)
            os.replace(tmp_path, cache_path)
            logger.info(
                f"Agent 缓存已写入: {cache_path} "
                f"({platform.value}, {len(agent_dicts)} agents, "
                f"profile_sha256={profile_sha256[:8] if profile_sha256 else 'None'}...)"
            )
            # 异步清理不在 save 中做(避免阻塞)
            return True
        except Exception as e:
            logger.error(f"save_cache 失败 ({platform.value}): {e}")
            return False

    @classmethod
    def load_cache_data(
        cls,
        sim_dir: str,
        platform: CachePlatform,
        profile_sha256: Optional[str] = None,
        config_sha256: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        读 cache 并返回 payload(dict)或 None(失效/不存在/损坏)。

        校验:
        - 文件存在
        - JSON 可解析
        - schema_version 匹配
        - 如传入 profile_sha256 / config_sha256,需与缓存中指纹一致
        """
        if not Config.AGENT_CACHE_ENABLED:
            return None

        cache_path = cls.get_cache_path(sim_dir, platform)
        if not os.path.isfile(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"load_cache: 读 {cache_path} 失败: {e}")
            return None

        # 版本校验
        if payload.get("schema_version") != cls.SCHEMA_VERSION:
            logger.warning(
                f"load_cache: schema_version={payload.get('schema_version')} "
                f"!= 当前 {cls.SCHEMA_VERSION},视为失效"
            )
            return None

        # hash 校验(只比对方传入的)
        if profile_sha256 is not None and payload.get("profile_sha256") != profile_sha256:
            logger.info(
                f"load_cache: profile sha256 不匹配 "
                f"(cached={payload.get('profile_sha256')[:8] if payload.get('profile_sha256') else None}, "
                f"current={profile_sha256[:8] if profile_sha256 else None}),视为失效"
            )
            return None

        if config_sha256 is not None and payload.get("config_sha256") != config_sha256:
            logger.info(
                f"load_cache: config sha256 不匹配,视为失效"
            )
            return None

        agents = payload.get("agents") or []
        if not agents:
            return None

        logger.info(
            f"Agent 缓存命中: {cache_path} ({platform.value}, "
            f"{len(agents)} agents)"
        )
        return payload

    # ============= 用户级 API(常用的快捷包装) =============

    @classmethod
    def invalidate_sim_cache(cls, sim_dir: str) -> int:
        """profile 重新生成时调,清掉该 sim 下所有 cache 文件。返回删除的文件数。"""
        cache_dir = cls.get_cache_dir(sim_dir)
        if not os.path.isdir(cache_dir):
            return 0
        deleted = 0
        try:
            for name in os.listdir(cache_dir):
                if name.endswith(f"_v{cls.SCHEMA_VERSION}.json"):
                    fp = os.path.join(cache_dir, name)
                    os.remove(fp)
                    deleted += 1
            logger.info(f"已失效 agent cache({sim_dir}): 删除 {deleted} 个文件")
        except OSError as e:
            logger.warning(f"invalidate_sim_cache 出错: {e}")
        return deleted

    @classmethod
    def cleanup_old_caches(cls, simulation_data_root: Optional[str] = None) -> int:
        """
        仿 Redis 清理:遍历所有 sim 的 cache 目录,
        1. 过期 mtime > TTL_DAYS -> 删
        2. 单 sim 超过 MAX_CACHE_PER_SIM 保留最近 N 个 -> 删旧的
        Returns 删除文件总数。
        """
        if simulation_data_root is None:
            simulation_data_root = Config.OASIS_SIMULATION_DATA_DIR

        ttl_seconds = max(1, int(Config.AGENT_CACHE_TTL_DAYS)) * 86400
        max_per_sim = max(1, int(Config.AGENT_CACHE_MAX_PER_SIM))

        if not os.path.isdir(simulation_data_root):
            return 0

        deleted = 0
        now_ts = datetime.now().timestamp()

        for sim_id in os.listdir(simulation_data_root):
            sim_dir = os.path.join(simulation_data_root, sim_id)
            if not os.path.isdir(sim_dir):
                continue
            cache_dir = cls.get_cache_dir(sim_dir)
            if not os.path.isdir(cache_dir):
                continue

            # 收集所有缓存文件
            cache_files = []
            try:
                for name in os.listdir(cache_dir):
                    if name.endswith(f"_v{cls.SCHEMA_VERSION}.json"):
                        fp = os.path.join(cache_dir, name)
                        mtime = os.path.getmtime(fp)
                        cache_files.append((fp, mtime))
            except OSError:
                continue

            # 1) 过期删除
            for fp, mtime in cache_files:
                if (now_ts - mtime) > ttl_seconds:
                    try:
                        os.remove(fp)
                        deleted += 1
                        logger.debug(f"过期删除: {fp}")
                    except OSError:
                        pass

            # 2) 超额删除(保留最近的 N 个)
            remaining = [(f, m) for f, m in cache_files if os.path.isfile(f)]
            remaining.sort(key=lambda x: x[1], reverse=True)  # 新的在前
            for fp, _ in remaining[max_per_sim:]:
                try:
                    os.remove(fp)
                    deleted += 1
                    logger.debug(f"超额删除: {fp}")
                except OSError:
                    pass

        if deleted:
            logger.info(f"cleanup_old_caches 完成: 删 {deleted} 文件")
        return deleted

    # ============= 内部辅助 =============

    @staticmethod
    def _serialize_user_info(user_info: Any) -> Dict[str, Any]:
        """UserInfo dataclass -> dict。失败回退 str() 容错。"""
        if user_info is None:
            return {}
        if isinstance(user_info, dict):
            return user_info
        try:
            from dataclasses import asdict, is_dataclass
            if is_dataclass(user_info):
                return asdict(user_info)
        except Exception:
            pass
        # 兜底:用 __dict__
        return dict(getattr(user_info, "__dict__", {}))

    @staticmethod
    def _serialize_actions(actions: Any) -> List[str]:
        """ActionType / Enum / FunctionTool / str -> list of str。

        兼容 OASIS SocialAgent.action_tools 是 FunctionTool 对象列表的情况——
        FunctionTool 的 action 名字在 `.func.__name__`,不能简单 str(它会得到 repr)。
        """
        if not actions:
            return []
        out: List[str] = []
        for a in actions:
            if a is None:
                continue
            if isinstance(a, str):
                out.append(a)
                continue
            # FunctionTool 包装类:camel 0.2.78 实际路径是 tool.func.__name__
            func = getattr(a, "func", None)
            if func is not None:
                name = getattr(func, "__name__", None) or getattr(a, "__name__", None)
                if name:
                    out.append(name)
                    continue
            # ActionType 枚举:取 .value
            v = getattr(a, "value", None)
            if v:
                out.append(v if isinstance(v, str) else str(v))
                continue
            # 兜底:跳过这个 — 宁可少一个 action 也不能写 repr
        return out
