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
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..config import Config
from ..models.task import TaskManager, TaskStatus
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
        """创建图谱"""
        store = GraphStore()
        store.create(name=name)
        return store.graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """设置图谱本体"""
        store = GraphStore(graph_id)

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

        store.set_ontology(
            entity_types=entity_types,
            edge_types=edge_types
        )

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
        分批添加文本到图谱，并提取实体和关系。

        Phase 4a 提速：
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

                # 优化 B1+B5：本批内 episode + 抽取出的实体/关系统一落盘一次
                # 业务语义不变：与原版"每 add_node 都 _save"产出的最终 JSON 完全一致
                store.flush()

            except Exception as e:
                if progress_callback:
                    progress_callback(t('progress.batchFailed', batch=batch_num, error=str(e)), 0)
                raise

        # 最终 flush（防御性：万一最后一批异常后仍有脏数据）
        store.flush()
        return episode_uuids

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

            entity_uuid_map: Dict[str, str] = {}  # 当前 chunk 内的 name → uuid

            # ============== 实体写入：单一临界区 ==============
            with seen_lock if seen_lock else _NullContext():
                # 进入临界区时一次性构建索引，避免每个实体都线性扫描全节点
                name_to_uuid: Dict[str, str] = {
                    n.name: n.uuid for n in store.get_all_nodes()
                }

                for entity in extraction_result.get("entities", []):
                    name = entity.get("name", "").strip()
                    entity_type = entity.get("type", "Entity").strip()
                    summary = entity.get("summary", "").strip()

                    if not name:
                        continue

                    # 跨批次去重
                    if name in seen_entity_names:
                        # O(1) 字典查替代原先 O(N) 线性扫描
                        existing_uuid = name_to_uuid.get(name)
                        if existing_uuid:
                            entity_uuid_map[name] = existing_uuid
                        continue

                    seen_entity_names.add(name)

                    # 确定标签
                    labels = [entity_type] if entity_type and entity_type != "Entity" else ["Entity"]
                    if entity_type not in ("Entity",) and entity_type not in labels:
                        labels.append(entity_type)

                    node_uuid = store.add_node(
                        name=name,
                        labels=labels,
                        summary=summary or f"{entity_type}: {name}",
                        attributes={"source": "llm_extraction"}
                    )
                    entity_uuid_map[name] = node_uuid
                    name_to_uuid[name] = node_uuid  # 同步更新本地索引，供后续实体/关系查

            # ============== 关系写入：单一临界区 ==============
            with seen_lock if seen_lock else _NullContext():
                # 重新构建索引：临界区之间其他 worker 可能已添加新节点
                name_to_uuid = {
                    n.name: n.uuid for n in store.get_all_nodes()
                }

                for relation in extraction_result.get("relations", []):
                    source_name = relation.get("source", "").strip()
                    target_name = relation.get("target", "").strip()
                    relation_type = relation.get("type", "RELATED_TO").strip()
                    fact = relation.get("fact", "").strip()

                    if not source_name or not target_name:
                        continue

                    # 优先用本 chunk 的映射；缺失则用全图索引
                    source_uuid = entity_uuid_map.get(source_name) or name_to_uuid.get(source_name)
                    target_uuid = entity_uuid_map.get(target_name) or name_to_uuid.get(target_name)

                    if source_uuid and target_uuid:
                        store.add_edge(
                            name=relation_type,
                            fact=fact or f"{source_name} {relation_type} {target_name}",
                            source_node_uuid=source_uuid,
                            target_node_uuid=target_uuid,
                            attributes={"source": "llm_extraction"}
                        )

        except Exception as e:
            logger.warning(f"实体提取失败（非致命）: {str(e)[:100]}")

    def _extract_entities_with_llm(
        self,
        text: str,
        entity_type_names: List[str],
        edge_type_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """使用 LLM 从文本中提取实体和关系"""

        entity_types_str = ", ".join(entity_type_names[:10]) if entity_type_names else "Person, Organization, Location, Event"
        edge_types_str = ", ".join(edge_type_names[:10]) if edge_type_names else "WORKS_FOR, LOCATED_IN, RELATED_TO, PARTICIPATES_IN"

        system_prompt = f"""你是一个知识图谱实体提取专家。从给定文本中提取实体和关系。

实体类型：{entity_types_str}
关系类型：{edge_types_str}

返回JSON格式：
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "summary": "简短描述"}}
    ],
    "relations": [
        {{"source": "源实体名称", "target": "目标实体名称", "type": "关系类型", "fact": "关系描述"}}
    ]
}}

规则：
1. 只提取文本中明确提到的实体
2. 实体类型必须是上面列出的类型之一
3. 关系类型必须是上面列出的类型之一
4. 实体名称使用文本中的原始名称
5. 返回空对象如果文本中没有可提取的实体"""

        user_prompt = f"请从以下文本中提取实体和关系：\n\n{text[:2000]}"

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            if isinstance(response, dict):
                return response
            return None

        except Exception as e:
            logger.debug(f"LLM 实体提取调用失败: {str(e)[:80]}")
            return None

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱信息"""
        store = GraphStore(graph_id)
        nodes = store.get_all_nodes()

        entity_types = set()
        for node in nodes:
            for label in node.labels:
                if label not in ("Entity", "Node", "Episode"):
                    entity_types.add(label)

        stats = store.get_statistics()
        return GraphInfo(
            graph_id=graph_id,
            node_count=stats["total_nodes"],
            edge_count=stats["total_edges"],
            entity_types=list(entity_types)
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据"""
        store = GraphStore(graph_id)
        nodes = store.get_all_nodes()
        edges = store.get_all_edges()

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
        """删除图谱"""
        store = GraphStore(graph_id)
        store.delete()
