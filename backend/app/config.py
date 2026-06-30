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
    
    # Zep配置（已移除依赖，保留兼容性）
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY', '')
    
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
    OASIS_DEFAULT_PARALLEL_PROFILE_COUNT = int(os.environ.get('OASIS_DEFAULT_PARALLEL_PROFILE_COUNT', '15'))
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

    # ========== 模拟快照抗风险配置（Step3 增强）==========
    # 周期性自动快照：监控线程每 N 轮触发一次，避免中途崩溃丢失全部进度
    # 业务不变性：snapshot 仅保存"过去数据"（已写入 actions.jsonl / db），
    # 恢复后从同一 start_round 重启 → 同一 prompt/温度 → 完全等价预测
    SIMULATION_AUTO_SNAPSHOT_ENABLED = os.environ.get('SIMULATION_AUTO_SNAPSHOT_ENABLED', 'true').lower() == 'true'
    SIMULATION_AUTO_SNAPSHOT_INTERVAL_ROUNDS = int(os.environ.get('SIMULATION_AUTO_SNAPSHOT_INTERVAL_ROUNDS', '5'))
    # 仅保留最近 K 个 auto 快照（手动快照永不自动清理）
    SIMULATION_AUTO_SNAPSHOTS_KEEP = int(os.environ.get('SIMULATION_AUTO_SNAPSHOTS_KEEP', '3'))
    
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
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        # ZEP_API_KEY 不再是必需项（已切换为本地图谱存储）
        return errors

