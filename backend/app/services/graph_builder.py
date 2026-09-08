"""
图谱构建服务
使用本地 GraphStore 构建知识图谱（替代 Zep Cloud）
包含 LLM 实体提取功能
"""

import os
import uuid
import json
import time
import threading
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from .graph_backend import get_graph_backend, get_graph_store
from .graph_store import GraphStore
from .text_processor import TextProcessor
from ..utils.llm_client import LLMClient
from ..utils.locale import t, get_locale, set_locale
from ..utils.logger import get_logger

logger = get_logger('mirofish.graph_builder')


class _NullContext:
    """空 context manager，用于 seen_lock 为 None 时兼容 `with lock or _NullContext()` 写法"""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    图谱构建服务
    负责使用本地 GraphStore 构建知识图谱
    包含 LLM 实体提取功能
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key 参数保留以兼容调用方，但不再需要
        self.task_manager = TaskManager()
        self._llm_client: Optional[LLMClient] = None

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """异步构建图谱"""
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        current_locale = get_locale()

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh'
    ):
        """图谱构建工作线程"""
        set_locale(locale)
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph')
            )

            # 1. 创建图谱
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=t('progress.graphCreated', graphId=graph_id)
            )

            # 2. 设置本体
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message=t('progress.ontologySet')
            )

            # 3. 文本分块
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=t('progress.textSplit', count=total_chunks)
            )

            # 4. 分批添加数据 + 实体提取（Phase 4a: chunk_parallel 提速）
            episode_uuids = self.add_text_batches(
                graph_id, chunks, ontology, batch_size,
                chunk_parallel=Config.GRAPH_BUILDER_CHUNK_PARALLEL,
                progress_callback=lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.65),  # 20-85%
                    message=msg
                )
            )

            # 4.5 等待第三方图谱后端完成服务端实体抽取
            self.wait_for_episodes(graph_id, episode_uuids)

            # 5. 获取图谱信息
            self.task_manager.update_task(
                task_id,
                progress=90,
                message=t('progress.fetchingGraphInfo')
            )

            graph_info = self._get_graph_info(graph_id)

            # 完成
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)

    def create_graph(self, name: str) -> str:
        """创建图谱（委托给当前 GRAPH_BACKEND）

        local: 创建本地图谱并落盘，返回 graph_id
        zep:   调用 Zep Cloud graph.create，返回 Zep 分配的 graph_id
        """
        backend = get_graph_backend(None) if Config.GRAPH_BACKEND == "zep" else None
        if backend is None:
            store = GraphStore()
            store.create(name=name)
            return store.graph_id
        return backend.create_graph(name=name, description="")

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """设置图谱本体（委托给当前 GRAPH_BACKEND）"""
        entity_types_raw = ontology.get("entity_types", [])
        edge_types_raw = ontology.get("edge_types", [])

        entity_types = {}
        if isinstance(entity_types_raw, list):
            for et in entity_types_raw:
                name = et.get("name", "")
                if name:
                    entity_types[name] = et
        elif isinstance(entity_types_raw, dict):
            entity_types = entity_types_raw

        edge_types = {}
        if isinstance(edge_types_raw, list):
            for et in edge_types_raw:
                name = et.get("name", "")
                if name:
                    edge_types[name] = et
        elif isinstance(edge_types_raw, dict):
            edge_types = edge_types_raw

        backend = get_graph_backend(graph_id)
        backend.set_ontology(entity_types=entity_types, edge_types=edge_types)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        ontology: Dict[str, Any],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
        chunk_parallel: int = 3,
    ) -> List[str]:
        """
        分批添加文本到图谱。

        - local 后端：在本地用 LLM 抽取实体/关系（保留历史行为，Phase 4a 并行加速）
        - zep 后端：仅做 add_batch，由 Zep 服务端异步完成实体抽取；
                    不会执行任何本地 LLM 抽取逻辑。

        Phase 4a 提速（仅 local 后端）：
        - 每个 batch 内的多个 chunk 并行调用 _extract_and_add_entities
        - chunk_parallel 控制单 batch 内的并发线程数（默认 = batch_size）
        - seen_entity_names 用 threading.Lock 保护，并发安全
        - LLM 调用 prompt/temperature 完全不变 → 预测准确度不变

        Args:
            graph_id: 图谱ID
            chunks: 文本块列表
            ontology: 本体定义（entity_types / edge_types）
            batch_size: 每个 batch 包含的 chunk 数
            progress_callback: 进度回调
            chunk_parallel: 单 batch 内 chunk 抽取的并行线程数（1=原行为）
        """
        # Zep 后端：纯 add_batch，实体抽取交给 Zep 服务端
        if Config.GRAPH_BACKEND == "zep":
            backend = get_graph_backend(graph_id)
            return backend.add_text_batches(
                texts=chunks,
                ontology=ontology,
                batch_size=batch_size,
                progress_callback=progress_callback,
                chunk_parallel=chunk_parallel,
            )

        # local 后端：保持原有并行抽取行为
        import concurrent.futures

        store = GraphStore(graph_id)
        episode_uuids = []
        total_chunks = len(chunks)

        # 准备本体信息用于实体提取
        entity_type_names = [et.get("name", "") for et in ontology.get("entity_types", []) if et.get("name")]
        edge_type_names = [et.get("name", "") for et in ontology.get("edge_types", []) if et.get("name")]

        # 用于跨批次去重的实体名称集合 + 锁
        seen_entity_names: set = set()
        seen_lock = threading.Lock()

        # Capture locale (LLM 调用可能在多线程 worker 中)
        current_locale = get_locale()

        def extract_one_chunk(chunk: str) -> None:
            """单 chunk 抽取（线程 worker）"""
            set_locale(current_locale)
            try:
                self._extract_and_add_entities(
                    store, chunk, entity_type_names, edge_type_names,
                    seen_entity_names, seen_lock,
                )
            except Exception as e:
                logger.warning(f"单 chunk 实体抽取失败（已跳过）: {str(e)[:200]}")

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks
                progress_callback(
                    t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=len(batch_chunks)),
                    progress
                )

            try:
                # 存储原始文本（保留串行：GraphStore 内部非线程安全）
                batch_uuids = store.add_batch(batch_chunks)
                episode_uuids.extend(batch_uuids)

                # 并行抽取实体和关系（Phase 4a 提速）
                workers = max(1, min(chunk_parallel, len(batch_chunks)))
                if workers == 1:
                    # 单线程：保留原行为，零开销
                    for chunk in batch_chunks:
                        extract_one_chunk(chunk)
                else:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                        futures = [executor.submit(extract_one_chunk, chunk) for chunk in batch_chunks]
                        # 等待所有完成（即使个别失败也不影响其他）
                        for f in concurrent.futures.as_completed(futures):
                            exc = f.exception()
                            if exc:
                                logger.warning(f"Chunk 抽取异常（已跳过）: {exc}")
                            # 修复（前端跳号）：每个 chunk 完成后立即 flush，
                            # 前端轮询就能看到逐步累加，不再等批末才一次性跳到 26
                            # 业务语义不变：仍是同一份 JSON，最终内容一致
                            #
                            # 修复（flush 与 worker 写入竞态）：flush 必须持有 seen_lock。
                            # worker 在 seen_lock 临界区内写 _nodes/_edges（add_node 的
                            # dict 插入），而主线程此处并发调用 flush → _save 迭代
                            # self._nodes.items() 时另一线程插入新 key 会抛
                            # RuntimeError: dictionary changed size during iteration，
                            # 异常从 flush 一路抛穿 build_task → 整个构建误标 FAILED。
                            # 拿同一把锁即可与全部写变异（upsert_entity/add_or_merge_edge）
                            # 互斥；等待期间只是推迟落盘，不影响正确性。
                            with seen_lock:
                                store.flush()

                # 优化 B1+B5：本批内 episode + 抽取出的实体/关系统一落盘一次
                # 业务语义不变：与原版"每 add_node 都 _save"产出的最终 JSON 完全一致
                # 注：上面已经在每个 chunk 完成后 flush，这里是兜底（episode 落盘）
                store.flush()

            except Exception as e:
                if progress_callback:
                    progress_callback(t('progress.batchFailed', batch=batch_num, error=str(e)), 0)
                raise

        # 最终 flush（防御性：万一最后一批异常后仍有脏数据）
        store.flush()
        return episode_uuids

    def wait_for_episodes(
        self,
        graph_id: str,
        episode_uuids: List[str],
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> None:
        """等待第三方图谱后端完成 episode 处理（仅 zep 模式生效）"""
        if not episode_uuids:
            return
        backend = get_graph_backend(graph_id)
        backend.wait_for_episodes(
            episode_uuids=episode_uuids,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    @staticmethod
    def _normalize_extracted_type(value: Any, allowed_types: List[str], fallback: str) -> str:
        """将 LLM 返回的类型限制在本体内，未知类型保留为通用类型。"""
        candidate = str(value or "").strip()
        if candidate in allowed_types:
            return candidate
        normalized = re.sub(r"[\s\-_]+", "", candidate).lower()
        for allowed in allowed_types:
            if re.sub(r"[\s\-_]+", "", allowed).lower() == normalized:
                return allowed
        return fallback

    @staticmethod
    def _normalize_extraction_result(
        extraction_result: Dict[str, Any],
        entity_type_names: List[str],
        edge_type_names: List[str],
    ) -> Dict[str, Any]:
        """清洗本地抽取结果，避免未知类型造成错误业务分类。"""
        entities = []
        for entity in extraction_result.get("entities", []) or []:
            if not isinstance(entity, dict):
                continue
            name = str(entity.get("name") or "").strip()
            if not name:
                continue
            item = dict(entity)
            item["name"] = name
            item["type"] = GraphBuilderService._normalize_extracted_type(
                item.get("type"), entity_type_names, "Entity"
            )
            item["summary"] = str(item.get("summary") or "").strip()
            entities.append(item)

        relations = []
        for relation in extraction_result.get("relations", []) or []:
            if not isinstance(relation, dict):
                continue
            source = str(relation.get("source") or "").strip()
            target = str(relation.get("target") or "").strip()
            if not source or not target:
                continue
            item = dict(relation)
            item["source"] = source
            item["target"] = target
            item["type"] = GraphBuilderService._normalize_extracted_type(
                item.get("type"), edge_type_names, "RELATED_TO"
            )
            item["fact"] = str(item.get("fact") or "").strip()
            relations.append(item)

        return {"entities": entities, "relations": relations}

    def _extract_and_add_entities(
        self,
        store: GraphStore,
        text: str,
        entity_type_names: List[str],
        edge_type_names: List[str],
        seen_entity_names: set,
        seen_lock: Optional[threading.Lock] = None,
    ):
        """从文本中提取实体和关系，并添加到图谱

        Phase 4a 并行化：
        - seen_lock 提供时，所有 seen_entity_names / store 写入都串行化
        - lock 为 None 时保持原单线程行为

        优化 B2：
        - 实体/关系处理各开一个临界区，临界区内一次构建 name→uuid 索引
        - 消除原先每次去重都对 store.get_all_nodes() 做 O(N) 线性扫描
        - 业务语义不变：仍是"去重 → 写入图谱"，仅查找方式由 O(N) 全表扫变成 O(1) 字典查
        - LLM 调用（_extract_entities_with_lllm）依旧在锁外，不阻塞并发
        """
        try:
            # 使用 LLM 提取实体和关系（在锁外执行，让并行 worker 不互相阻塞）
            extraction_result = self._extract_entities_with_llm(
                text, entity_type_names, edge_type_names
            )

            if not extraction_result:
                return

            extraction_result = self._normalize_extraction_result(
                extraction_result,
                entity_type_names,
                edge_type_names,
            )

            # Phase 4b：LLM 别名合并（默认关闭，需 GRAPH_LLM_MERGE_ENABLED=true 才生效）
            # 作用：让 LLM 判断 chunk 内 + 与已有节点之间的别名/简称/英文是否同一实体，返回合并映射
            # 应用：对 entities 和 relations 的 name 字段做原地替换，再走原有 upsert_entity 流程
            # 成本：每 chunk 1 次 LLM 调用；默认不开启，避免构建图谱时持续花钱
            if Config.GRAPH_LLM_MERGE_ENABLED:
                existing_names = [
                    n.name for n in store.get_all_nodes()
                    if "Episode" not in n.labels
                ]
                merge_map = self._merge_entities_with_llm(
                    extraction_result.get("entities", []) or [],
                    existing_names,
                )
                if merge_map:
                    for entity in extraction_result.get("entities", []) or []:
                        n = entity.get("name")
                        if n in merge_map:
                            entity["name"] = merge_map[n]
                    for relation in extraction_result.get("relations", []) or []:
                        for k in ("source", "target"):
                            v = relation.get(k)
                            if v in merge_map:
                                relation[k] = merge_map[v]
                    logger.info(f"LLM 别名合并: 合并 {len(merge_map)} 对实体")

            entity_uuid_map: Dict[str, str] = {}  # 当前 chunk 内的 name → uuid

            # ============== 实体写入：单一临界区 ==============
            with seen_lock if seen_lock else _NullContext():
                # 进入临界区时一次性构建索引，避免每个实体都线性扫描全节点
                name_to_uuid: Dict[str, str] = {}
                for existing_node in store.get_all_nodes():
                    names = [existing_node.name] + list(existing_node.attributes.get("aliases", []))
                    for existing_name in names:
                        name_to_uuid[store.normalize_entity_name(existing_name)] = existing_node.uuid

                for entity in extraction_result.get("entities", []):
                    name = entity.get("name", "").strip()
                    entity_type = entity.get("type", "Entity").strip()
                    summary = entity.get("summary", "").strip()

                    if not name:
                        continue

                    labels = [entity_type] if entity_type and entity_type != "Entity" else ["Entity"]
                    match_keys = store.entity_match_keys(name, labels)
                    if not match_keys:
                        continue

                    existing_uuid = next((name_to_uuid.get(key) for key in match_keys if name_to_uuid.get(key)), None)
                    if existing_uuid:
                        entity_uuid_map[name] = existing_uuid
                        entity_uuid_map[store.normalize_entity_name(name)] = existing_uuid
                        seen_entity_names.update(match_keys)
                        continue

                    node_uuid = store.upsert_entity(
                        name=name,
                        labels=labels,
                        summary=summary or f"{entity_type}: {name}",
                        attributes={"source": "llm_extraction"},
                    )
                    entity_uuid_map[name] = node_uuid
                    entity_uuid_map[store.normalize_entity_name(name)] = node_uuid
                    seen_entity_names.update(match_keys)
                    for key in match_keys:
                        name_to_uuid[key] = node_uuid

            # ============== 关系写入：单一临界区 ==============
            with seen_lock if seen_lock else _NullContext():
                # 重新构建索引：临界区之间其他 worker 可能已添加新节点
                name_to_uuid: Dict[str, str] = {}
                for existing_node in store.get_all_nodes():
                    names = [existing_node.name] + list(existing_node.attributes.get("aliases", []))
                    for existing_name in names:
                        name_to_uuid[store.normalize_entity_name(existing_name)] = existing_node.uuid

                for relation in extraction_result.get("relations", []):
                    source_name = relation.get("source", "").strip()
                    target_name = relation.get("target", "").strip()
                    relation_type = relation.get("type", "RELATED_TO").strip()
                    fact = relation.get("fact", "").strip()

                    if not source_name or not target_name:
                        continue

                    source_uuid = (
                        entity_uuid_map.get(source_name)
                        or entity_uuid_map.get(store.normalize_entity_name(source_name))
                        or name_to_uuid.get(store.normalize_entity_name(source_name))
                    )
                    target_uuid = (
                        entity_uuid_map.get(target_name)
                        or entity_uuid_map.get(store.normalize_entity_name(target_name))
                        or name_to_uuid.get(store.normalize_entity_name(target_name))
                    )

                    if source_uuid and target_uuid:
                        store.add_or_merge_edge(
                            name=relation_type,
                            fact=fact or f"{source_name} {relation_type} {target_name}",
                            source_node_uuid=source_uuid,
                            target_node_uuid=target_uuid,
                            attributes={"source": "llm_extraction"},
                        )

        except Exception as e:
            logger.warning(f"实体提取失败（非致命）: {str(e)[:100]}")

    def _extract_entities_with_llm(
        self,
        text: str,
        entity_type_names: List[str],
        edge_type_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """使用 LLM 从文本中提取实体和关系

        修复（超长 chunk 静默截断）：原实现 text[:2000] 直接截断，当 chunk_size
        配置超过 2000 字符时，尾部内容被静默丢弃且无任何提示。
        现改为：超长文本分段抽取后合并结果。跨段重复实体会被调用方
        _extract_and_add_entities 的 seen_entity_names/name_to_uuid 去重机制
        合并，因此此处无需去重。段间保留少量重叠，缓解跨段边界关系丢失。
        默认 chunk_size=500 不超过阈值，仍走单次调用，行为完全不变。
        """
        MAX_CHARS_PER_CALL = 2000
        SEGMENT_OVERLAP = 200

        if len(text) <= MAX_CHARS_PER_CALL:
            return self._extract_entities_with_llm_once(
                text, entity_type_names, edge_type_names
            )

        step = MAX_CHARS_PER_CALL - SEGMENT_OVERLAP
        segments = [text[i:i + MAX_CHARS_PER_CALL] for i in range(0, len(text), step)]
        logger.info(
            f"超长 chunk ({len(text)} 字符) 分 {len(segments)} 段抽取"
            f"（原实现会静默丢弃尾部 {len(text) - MAX_CHARS_PER_CALL} 字符）"
        )

        merged: Dict[str, Any] = {"entities": [], "relations": []}
        for segment in segments:
            part = self._extract_entities_with_llm_once(
                segment, entity_type_names, edge_type_names
            )
            if not part:
                continue
            merged["entities"].extend(part.get("entities", []) or [])
            merged["relations"].extend(part.get("relations", []) or [])
        return merged

    def _extract_entities_with_llm_once(
        self,
        text: str,
        entity_type_names: List[str],
        edge_type_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """单次 LLM 实体关系抽取（text 由调用方保证不超过 2000 字符）"""
        entity_types_str = ", ".join(entity_type_names[:10]) if entity_type_names else "Person, Organization, Location, Event"
        edge_types_str = ", ".join(edge_type_names[:10]) if edge_type_names else "WORKS_FOR, LOCATED_IN, RELATED_TO, PARTICIPATES_IN"

        system_prompt = f"""你是高召回率的知识图谱事实抽取专家。请从给定文本中尽可能完整地抽取实体、事件、事实和关系，供后续 Agent 人设、模拟和报告检索使用。

本体中的业务实体类型：{entity_types_str}
本体中的业务关系类型：{edge_types_str}

返回严格 JSON：
{{
    "entities": [
        {{"name": "实体原文名称", "type": "实体类型", "summary": "基于文本的简短事实描述"}}
    ],
    "relations": [
        {{"source": "源实体名称", "target": "目标实体名称", "type": "关系类型", "fact": "文本明确支持的关系事实"}}
    ]
}}

抽取规则：
1. 高召回：抽取文本中有实际意义的公司、机构、人物、群体、事件、岗位、产品、法律法规、报告、股票代码、金额、比例、时间节点和业务概念。
2. 不要因为实体不是人物或组织就丢弃；无法匹配业务实体类型时，type 使用 Entity。
3. 只有能够明确对应本体业务类型时，才使用本体中的业务类型；不要为了凑类型把普通公司、金额或事件硬分类成其他业务类型。
4. 关系类型能够对应本体时使用本体类型，否则使用 RELATED_TO；不要丢弃有明确事实依据的关系。
5. 同一实体在不同表达中尽量使用文本中的完整名称；简称、别名、股票代码等仍然作为实体或别名信息保留。
6. 只抽取文本明确支持的事实，不要推测或补写文本外信息。
7. 一个文本块没有可抽取内容时返回空数组，不要返回额外说明。"""

        user_prompt = f"请从以下文本中提取实体和关系：\n\n{text}"

        # 修复（单 chunk 抽取失败无重试）：原实现 LLM 调用一次失败（限流/网络抖动/
        # 输出格式异常）即放弃，该 chunk 的实体关系永久缺失。
        # 现改为最多 3 次尝试 + 线性退避（1s/2s）。LLM 瞬时故障占绝大多数，
        # 一次重试通常即可恢复；最终失败才放弃该段（warning 提醒数据缺口）。
        # sleep 只阻塞当前 worker 线程，同批其他 chunk 不受影响。
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = self.llm.chat_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4000  # 提升到 4000：高召回 Prompt 在 chunk 内容密集时（公司/法规/报告/金额等）会输出 30+ 实体，原 2000 容易被截断成无效 JSON
                )

                if isinstance(response, dict):
                    return response
                # 非 dict（含 None）：多为输出格式异常，属瞬时故障，同样重试
                err_desc = f"响应格式非 dict: {type(response).__name__}"

            except Exception as e:
                err_desc = str(e)[:80]

            if attempt < max_attempts:
                wait = attempt  # 1s, 2s
                logger.warning(
                    f"LLM 实体提取失败（第 {attempt}/{max_attempts} 次），{wait}s 后重试: {err_desc}"
                )
                time.sleep(wait)
            else:
                logger.warning(
                    f"LLM 实体提取重试 {max_attempts} 次后仍失败，放弃该文本段（数据缺失）: {err_desc}"
                )

        return None

    def _merge_entities_with_llm(
        self,
        chunk_entities: List[Dict[str, Any]],
        existing_names: List[str],
    ) -> Dict[str, str]:
        """让 LLM 判断别名 / 简称 / 英文 / 繁体是否同一实体，返回 source_name → canonical_name 映射。

        - 输入：本 chunk 抽出的 entities + 已有节点名列表
        - 输出：dict，key=待合并的源实体名，value=目标实体名（canonical）
        - 失败 / 无合并：返回 {}
        - 业务语义：调用方负责把 source_name 替换为 canonical_name 再走 upsert_entity
        """
        if not Config.GRAPH_LLM_MERGE_ENABLED:
            return {}
        if not chunk_entities:
            return {}

        # 收集待判定的实体名（chunk 内 + 已有节点），去重
        chunk_names = []
        seen = set()
        for e in chunk_entities:
            n = str(e.get("name") or "").strip()
            if n and n not in seen:
                chunk_names.append(n)
                seen.add(n)

        all_names = chunk_names + [
            n for n in existing_names if n and n not in seen and not seen.add(n)
        ]
        if len(all_names) < 2:
            return {}

        names_str = "\n".join(f"- {n}" for n in all_names[:200])

        system_prompt = """你是实体归一化专家。下面给出一组实体名称（可能来自不同文本块），请判断哪些名称在事实层面指向同一个真实世界实体。

合并判定标准（严格）：
1. 同一公司 / 机构：全称 vs 简称、繁体 vs 简体、中文 vs 英文官方名（例如 "大众汽车" ↔ "Volkswagen"）
2. 同一人物：全名 vs 姓名 vs 昵称（必须文本明确指向同一人，不能猜测）
3. 同一产品 / 法规 / 报告：全名 vs 常见简称

不合并的标准（严格）：
- 只是包含关系但不是同实体（例如 "中国" ⊂ "中国人民银行" 不合并）
- 文本未明确指向同一实体的，倾向不合并
- 数字 / 年份 / 量词差异（如 "2026届应届生" 与 "107名应届生"）如果无法确定是同一群体，不合并

返回严格 JSON：
{"merges": [{"keep": "保留的规范名（较长/较完整的那个）", "merge": "被合并的名字"}, ...]}

没有合并就返回 {"merges": []}。不要返回额外说明。"""

        user_prompt = (
            "请判断下列实体名之间的合并关系：\n\n"
            f"{names_str}\n\n"
            "只输出合并对，保留名选较长较完整的；无法确定的不要输出。"
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=800,
            )
            if not isinstance(response, dict):
                return {}

            valid_names = set(all_names)
            result: Dict[str, str] = {}
            for item in response.get("merges", []) or []:
                if not isinstance(item, dict):
                    continue
                keep = str(item.get("keep") or "").strip()
                merge = str(item.get("merge") or "").strip()
                if not keep or not merge or keep == merge:
                    continue
                # 严格校验：keep / merge 必须都在候选列表里，避免幻觉
                if keep not in valid_names or merge not in valid_names:
                    continue
                result[merge] = keep
            return result

        except Exception as e:
            logger.debug(f"LLM 别名合并失败（已跳过）: {str(e)[:80]}")
            return {}

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱信息"""
        backend = get_graph_backend(graph_id)
        nodes = backend.get_all_nodes()

        entity_types = set()
        for node in nodes:
            for label in node.labels:
                if label not in ("Entity", "Node", "Episode"):
                    entity_types.add(label)

        stats = backend.get_statistics()
        return GraphInfo(
            graph_id=graph_id,
            node_count=stats["total_nodes"],
            edge_count=stats["total_edges"],
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据"""
        backend = get_graph_backend(graph_id)
        nodes = backend.get_all_nodes()
        edges = backend.get_all_edges()

        # 过滤掉 Episode 节点
        real_nodes = [n for n in nodes if "Episode" not in n.labels]

        nodes_data = [n.to_dict() for n in real_nodes]
        edges_data = [e.to_dict() for e in edges]

        # 构建节点名映射
        node_map = {n.uuid: n.name for n in real_nodes}
        for edge_item in edges_data:
            edge_item["source_node_name"] = node_map.get(edge_item["source_node_uuid"], "")
            edge_item["target_node_name"] = node_map.get(edge_item["target_node_uuid"], "")

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        """删除图谱（委托给当前 GRAPH_BACKEND）"""
        backend = get_graph_backend(graph_id)
        backend.delete_graph(graph_id)
