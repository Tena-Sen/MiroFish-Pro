"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep配置（仅在 GRAPH_BACKEND=zep 时使用）
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY', '')

    # 图谱后端选择：local (默认，本地 GraphStore) 或 zep (Zep Cloud Standalone Graph)
    GRAPH_BACKEND = os.environ.get('GRAPH_BACKEND', 'local').lower().strip()
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    # 并行配置 - 根据LLM API并发限制调整
    OASIS_DEFAULT_PARALLEL_PROFILE_COUNT = int(os.environ.get('OASIS_DEFAULT_PARALLEL_PROFILE_COUNT', '30'))
    # Phase 2: 异步 profile 生成的默认并发数（高于 ThreadPool 是因为 AsyncOpenAI 不阻塞事件循环）
    OASIS_ASYNC_PROFILE_CONCURRENCY = int(os.environ.get('OASIS_ASYNC_PROFILE_CONCURRENCY', '40'))
    # 是否默认走异步路径（Phase 2 提速）
    OASIS_USE_ASYNC_PROFILE_GEN = os.environ.get('OASIS_USE_ASYNC_PROFILE_GEN', 'true').lower() == 'true'

    # 报告生成并行度（Phase 3）
    # 1 = 完全串行（原行为，章节连贯性最强）
    # N = 每 N 个章节一组并行（提速约 N 倍，但跨章节连贯性略降）
    REPORT_DEFAULT_WAVE_SIZE = int(os.environ.get('REPORT_DEFAULT_WAVE_SIZE', '2'))
    REPORT_MAX_WAVE_SIZE = int(os.environ.get('REPORT_MAX_WAVE_SIZE', '5'))

    # 优化 C7：Chat with Report Agent 时报告内容截断长度
    # 超过此长度的报告会在 chat prompt 中被截断；值越大上下文越丰富但 token 成本越高
    REPORT_CHAT_CONTEXT_MAX_CHARS = int(os.environ.get('REPORT_CHAT_CONTEXT_MAX_CHARS', '15000'))

    # 图谱构建 chunk 并行度（Phase 4a）
    # 1 = 单 chunk 串行（原行为）
    # N = 单 batch 内 N 个 chunk 并行抽取实体/关系
    GRAPH_BUILDER_CHUNK_PARALLEL = int(os.environ.get('GRAPH_BUILDER_CHUNK_PARALLEL', '3'))

    # 图谱构建 LLM 别名合并（Phase 4b）
    # True  = 每 chunk 抽取完让 LLM 判断别名 / 简称 / 英文是否同一实体，再复用 UUID
    # False = 仅靠 entity_match_keys 规则（NFKC + 公司后缀），无 LLM 调用
    # 默认 False：避免每次构建都花钱；开启后预期 97 → 50~70 实体
    GRAPH_LLM_MERGE_ENABLED = os.environ.get('GRAPH_LLM_MERGE_ENABLED', 'false').lower() == 'true'

    # ========== 模拟快照抗风险配置（Step3 增强）==========
    # 周期性自动快照：监控线程每 N 轮触发一次，避免中途崩溃丢失全部进度
    # 业务不变性：snapshot 仅保存"过去数据"（已写入 actions.jsonl / db），
    # 恢复后从同一 start_round 重启 → 同一 prompt/温度 → 完全等价预测
    SIMULATION_AUTO_SNAPSHOT_ENABLED = os.environ.get('SIMULATION_AUTO_SNAPSHOT_ENABLED', 'true').lower() == 'true'
    SIMULATION_AUTO_SNAPSHOT_INTERVAL_ROUNDS = int(os.environ.get('SIMULATION_AUTO_SNAPSHOT_INTERVAL_ROUNDS', '5'))
    # 仅保留最近 K 个 auto 快照（手动快照永不自动清理）
    SIMULATION_AUTO_SNAPSHOTS_KEEP = int(os.environ.get('SIMULATION_AUTO_SNAPSHOTS_KEEP', '3'))

    # Agent persona 缓存（chat-only 启动加速用）
    # 把 user_info + available_actions 落到磁盘 json,跳过 320 个 SocialAgent 重新实例化
    AGENT_CACHE_ENABLED = os.environ.get('AGENT_CACHE_ENABLED', 'true').lower() == 'true'
    AGENT_CACHE_TTL_DAYS = int(os.environ.get('AGENT_CACHE_TTL_DAYS', '7'))
    AGENT_CACHE_MAX_PER_SIM = int(os.environ.get('AGENT_CACHE_MAX_PER_SIM', '3'))

    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置"""
        errors: list[str] = []

        # === 必填项 ===
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        # ZEP_API_KEY 不再是必需项（已切换为本地图谱存储）
        # 仅在 GRAPH_BACKEND=zep 时才要求配置 ZEP_API_KEY
        if cls.GRAPH_BACKEND not in ("local", "zep"):
            errors.append(
                f"GRAPH_BACKEND 非法: {cls.GRAPH_BACKEND!r}，仅支持 'local' 或 'zep'"
            )
        if cls.GRAPH_BACKEND == "zep" and not cls.ZEP_API_KEY:
            errors.append("GRAPH_BACKEND=zep 时必须配置 ZEP_API_KEY")

        # === 占位符 / 格式校验（防踩隐形坑） ===
        # 触发条件: 用户在 .env 里写了占位符、值带前后空白、或 URL 路径异常
        # 这些都会原样进 os.environ,被 OpenAI SDK 当成真实值发出去
        # 表现: 404 page not found / 403 authorization failed / "model not found" 等
        # 难定位,所以在启动时直接 fail-fast
        suspicious_patterns = (
            "__TODO__", "TODO", "YOUR-API-KEY", "YOUR_KEY",
            "FILL-IN", "REPLACE-ME", "PLEASE-FILL", "XXXXX",
            "填写", "替换", "请填", "占位",
        )

        def _check(name: str, value: str | None, *, allow_empty: bool = False) -> None:
            """单字段校验：占位符 / 前后空白 / 空值"""
            if value is None or value == "":
                if allow_empty:
                    return
                errors.append(f"{name} 未配置")
                return
            if value != value.strip():
                # python-dotenv 不会自动 strip,值带前/后空格会原样读进来
                errors.append(f"{name} 包含前后空白字符: {value!r}")
            upper = value.upper()
            for pat in suspicious_patterns:
                if pat.upper() in upper:
                    errors.append(
                        f"{name} 看起来是占位符 ({pat!r})，"
                        f"未真实填写: {value!r}"
                    )
                    break

        # 通用 LLM_* 必须填
        _check("LLM_API_KEY", cls.LLM_API_KEY)
        _check("LLM_BASE_URL", cls.LLM_BASE_URL)
        _check("LLM_MODEL_NAME", cls.LLM_MODEL_NAME)

        return errors

