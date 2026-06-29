"""
本地知识图谱存储服务
使用 NetworkX + TF-IDF 实现，替代 Zep Cloud 的 Standalone Graph 功能
零外部服务依赖，无限额限制
"""

import os
import uuid
import json
import time
import threading
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

import networkx as nx

from ..utils.logger import get_logger
from ..utils.atomic_io import atomic_write_json

logger = get_logger('mirofish.graph_store')

# ============== 数据结构 ==============

@dataclass
class NodeData:
    """节点数据"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }


@dataclass
class EdgeData:
    """边数据"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    episodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
            "episodes": self.episodes,
        }


@dataclass
class OntologyDef:
    """本体定义"""
    entity_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edge_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ============== 图谱存储 ==============

class GraphStore:
    """
    本地知识图谱存储

    使用 NetworkX 管理图结构，TF-IDF 实现语义搜索，
    JSON 文件实现持久化。
    """

    # 单例：所有实例共享同一个存储目录
    _store_dir: str = os.path.join(os.path.dirname(__file__), '../../uploads/graphs')
    _lock = threading.Lock()

    def __init__(self, graph_id: Optional[str] = None):
        """
        初始化图谱存储

        Args:
            graph_id: 图谱ID，如果不提供则自动创建
        """
        if graph_id:
            self.graph_id = graph_id
        else:
            self.graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"

        self._graph = nx.DiGraph()
        self._nodes: Dict[str, NodeData] = {}
        self._edges: Dict[str, EdgeData] = {}
        self._ontology = OntologyDef()
        self._name: str = ""
        self._description: str = ""

        # TF-IDF 搜索索引（延迟构建）
        self._tfidf_matrix = None
        self._tfidf_vectorizer = None
        self._tfidf_doc_ids: List[str] = []  # 文档ID列表（node_uuid 或 edge_uuid）
        self._tfidf_doc_types: List[str] = []  # "node" 或 "edge"
        self._tfidf_dirty = True

        # 脏标记（性能优化）：add_node/add_edge 只标脏，由调用方按需 flush()
        # 业务语义不变：构造图（create）/本体设置（set_ontology）/批末（add_batch/flush）仍保证落盘
        self._dirty: bool = False

        # 确保存储目录存在
        os.makedirs(self._store_dir, exist_ok=True)

        # 如果已有持久化数据则加载
        self._load_if_exists()

    # ========== 图谱生命周期 ==========

    def create(self, name: str = "MiroFish Graph", description: str = ""):
        """创建新图谱"""
        self._name = name
        self._description = description
        self._save()
        logger.info(f"创建图谱: {self.graph_id} ({name})")

    def delete(self):
        """删除图谱"""
        path = self._data_path()
        if os.path.exists(path):
            os.remove(path)
        logger.info(f"删除图谱: {self.graph_id}")

    def exists(self) -> bool:
        """检查图谱是否存在"""
        return os.path.exists(self._data_path())

    # ========== 本体管理 ==========

    def set_ontology(self, entity_types: Dict[str, Any], edge_types: Dict[str, Any]):
        """
        设置图谱本体定义

        Args:
            entity_types: 实体类型定义 {name: {description, attributes}}
            edge_types: 边类型定义 {name: {description, source_targets, attributes}}
        """
        # 转换为简化格式存储
        for name, cls_or_info in entity_types.items():
            if isinstance(cls_or_info, type):
                # 从 Pydantic 模型类提取信息
                desc = cls_or_info.__doc__ or f"A {name} entity."
                attrs = {}
                for field_name, field_info in cls_or_info.model_fields.items():
                    attrs[field_name] = field_info.description or field_name
                self._ontology.entity_types[name] = {
                    "description": desc,
                    "attributes": attrs
                }
            elif isinstance(cls_or_info, dict):
                self._ontology.entity_types[name] = cls_or_info

        for name, info in edge_types.items():
            if isinstance(info, tuple) and len(info) == 2:
                edge_cls, source_targets = info
                desc = edge_cls.__doc__ or f"A {name} relationship."
                self._ontology.edge_types[name] = {
                    "description": desc,
                    "source_targets": [
                        {"source": st.source, "target": st.target}
                        for st in source_targets
                    ]
                }
            elif isinstance(info, dict):
                self._ontology.edge_types[name] = info

        self._save()
        logger.info(f"设置本体: {len(self._ontology.entity_types)} 实体类型, {len(self._ontology.edge_types)} 关系类型")

    # ========== 节点操作 ==========

    def add_node(self, name: str, labels: List[str], summary: str = "",
                 attributes: Dict[str, Any] = None, node_uuid: str = None) -> str:
        """添加节点（仅标脏，由调用方按需 flush() 落盘）"""
        node_uuid = node_uuid or str(uuid.uuid4())
        node = NodeData(
            uuid=node_uuid,
            name=name,
            labels=labels,
            summary=summary,
            attributes=attributes or {},
        )
        self._nodes[node_uuid] = node
        self._graph.add_node(node_uuid, name=name, labels=labels)
        self._tfidf_dirty = True
        # 优化：不再每次 _save()，仅标脏；批末/生命周期点会 flush()
        self._dirty = True
        return node_uuid

    def get_node(self, node_uuid: str) -> Optional[NodeData]:
        """获取节点"""
        return self._nodes.get(node_uuid)

    def get_all_nodes(self) -> List[NodeData]:
        """获取所有节点"""
        return list(self._nodes.values())

    def get_nodes_by_graph_id(self, graph_id: str, limit: int = 100,
                               uuid_cursor: str = None) -> List[NodeData]:
        """分页获取节点（兼容 Zep API 接口）"""
        nodes = list(self._nodes.values())
        if uuid_cursor:
            # 找到 cursor 位置
            start_idx = 0
            for i, n in enumerate(nodes):
                if n.uuid == uuid_cursor:
                    start_idx = i + 1
                    break
            nodes = nodes[start_idx:]
        return nodes[:limit]

    # ========== 边操作 ==========

    def add_edge(self, name: str, fact: str, source_node_uuid: str,
                 target_node_uuid: str, attributes: Dict[str, Any] = None,
                 edge_uuid: str = None, episodes: List[str] = None) -> str:
        """添加边（仅标脏，由调用方按需 flush() 落盘）"""
        edge_uuid = edge_uuid or str(uuid.uuid4())
        edge = EdgeData(
            uuid=edge_uuid,
            name=name,
            fact=fact,
            source_node_uuid=source_node_uuid,
            target_node_uuid=target_node_uuid,
            attributes=attributes or {},
            episodes=episodes or [],
        )
        self._edges[edge_uuid] = edge
        self._graph.add_edge(source_node_uuid, target_node_uuid, uuid=edge_uuid, name=name)
        self._tfidf_dirty = True
        # 优化：不再每次 _save()，仅标脏；批末/生命周期点会 flush()
        self._dirty = True
        return edge_uuid

    def get_edge(self, edge_uuid: str) -> Optional[EdgeData]:
        """获取边"""
        return self._edges.get(edge_uuid)

    def get_all_edges(self) -> List[EdgeData]:
        """获取所有边"""
        return list(self._edges.values())

    def get_edges_by_graph_id(self, graph_id: str, limit: int = 100,
                               uuid_cursor: str = None) -> List[EdgeData]:
        """分页获取边（兼容 Zep API 接口）"""
        edges = list(self._edges.values())
        if uuid_cursor:
            start_idx = 0
            for i, e in enumerate(edges):
                if e.uuid == uuid_cursor:
                    start_idx = i + 1
                    break
            edges = edges[start_idx:]
        return edges[:limit]

    def get_node_edges(self, node_uuid: str) -> List[EdgeData]:
        """获取节点相关的所有边"""
        result = []
        for edge in self._edges.values():
            if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                result.append(edge)
        return result

    # ========== 批量添加（兼容 Zep add_batch） ==========

    def add_batch(self, texts: List[str]) -> List[str]:
        """
        批量添加文本数据

        本地方案：直接将文本作为 episode 存储，
        后续由 LLM 或规则引擎提取实体和关系。

        优化：循环内 add_node 不再逐次落盘，循环结束统一 flush() 一次。

        Args:
            texts: 文本列表

        Returns:
            episode UUID 列表
        """
        episode_uuids = []
        for text in texts:
            ep_uuid = str(uuid.uuid4())
            # 作为特殊节点存储，标记为 episode
            self.add_node(
                name=f"episode_{ep_uuid[:8]}",
                labels=["Episode"],
                summary=text,
                attributes={"type": "episode", "raw_text": text},
                node_uuid=ep_uuid,
            )
            episode_uuids.append(ep_uuid)
        # 批末统一落盘（优化前：N 次 _save() + 1 次；优化后：1 次）
        self.flush()
        return episode_uuids

    def add_single_episode(self, text: str, episode_type: str = "text") -> str:
        """添加单条 episode（兼容 Zep graph.add）—— 独立 API，调用即落盘"""
        ep_uuid = str(uuid.uuid4())
        self.add_node(
            name=f"episode_{ep_uuid[:8]}",
            labels=["Episode"],
            summary=text,
            attributes={"type": episode_type, "raw_text": text},
            node_uuid=ep_uuid,
        )
        # add_single_episode 是单条独立 API（zep_graph_memory_updater.py 等调用方依赖其立即落盘的语义）
        self.flush()
        return ep_uuid

    def flush(self) -> None:
        """将脏数据落盘。无脏数据时是 no-op。

        设计：仅 _save() 一次，原子写入，不破坏既有持久化语义。
        """
        if self._dirty:
            self._save()
            self._dirty = False

    # ========== 搜索（TF-IDF 语义搜索） ==========

    def search(self, query: str, limit: int = 10, scope: str = "edges") -> Dict[str, Any]:
        """
        语义搜索（基于 TF-IDF）

        Args:
            query: 搜索查询
            limit: 返回结果数量
            scope: "edges", "nodes", 或 "both"

        Returns:
            搜索结果 {edges: [...], nodes: [...]}
        """
        self._ensure_tfidf_index()

        result = {"edges": [], "nodes": []}

        if self._tfidf_matrix is None or self._tfidf_matrix.shape[0] == 0:
            return result

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            query_vec = self._tfidf_vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

            # 按分数排序
            scored_indices = sorted(
                range(len(scores)),
                key=lambda i: scores[i],
                reverse=True
            )

            for idx in scored_indices:
                if scores[idx] < 0.01:  # 最低相似度阈值
                    break

                doc_id = self._tfidf_doc_ids[idx]
                doc_type = self._tfidf_doc_types[idx]

                if doc_type == "edge" and scope in ("edges", "both"):
                    edge = self._edges.get(doc_id)
                    if edge:
                        result["edges"].append(edge.to_dict())
                elif doc_type == "node" and scope in ("nodes", "both"):
                    node = self._nodes.get(doc_id)
                    if node and "Episode" not in node.labels:
                        result["nodes"].append(node.to_dict())

                if len(result["edges"]) >= limit and len(result["nodes"]) >= limit:
                    break

        except Exception as e:
            logger.warning(f"TF-IDF 搜索失败，降级为关键词匹配: {e}")
            return self._keyword_search(query, limit, scope)

        # 限制数量
        result["edges"] = result["edges"][:limit]
        result["nodes"] = result["nodes"][:limit]
        return result

    def _keyword_search(self, query: str, limit: int, scope: str) -> Dict[str, Any]:
        """关键词匹配搜索（降级方案）"""
        result = {"edges": [], "nodes": []}
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            if not text:
                return 0
            text_lower = text.lower()
            if query_lower in text_lower:
                return 100
            return sum(10 for kw in keywords if kw in text_lower)

        if scope in ("edges", "both"):
            scored = [(match_score(e.fact) + match_score(e.name), e)
                      for e in self._edges.values()]
            scored.sort(key=lambda x: x[0], reverse=True)
            result["edges"] = [e.to_dict() for s, e in scored[:limit] if s > 0]

        if scope in ("nodes", "both"):
            scored = [(match_score(n.name) + match_score(n.summary), n)
                      for n in self._nodes.values() if "Episode" not in n.labels]
            scored.sort(key=lambda x: x[0], reverse=True)
            result["nodes"] = [n.to_dict() for s, n in scored[:limit] if s > 0]

        return result

    def _ensure_tfidf_index(self):
        """确保 TF-IDF 索引已构建"""
        if not self._tfidf_dirty and self._tfidf_vectorizer is not None:
            return

        with self._lock:
            if not self._tfidf_dirty and self._tfidf_vectorizer is not None:
                return

            try:
                from sklearn.feature_extraction.text import TfidfVectorizer

                documents = []
                doc_ids = []
                doc_types = []

                # 收集边文档
                for edge in self._edges.values():
                    text = f"{edge.name} {edge.fact}"
                    if text.strip():
                        documents.append(text)
                        doc_ids.append(edge.uuid)
                        doc_types.append("edge")

                # 收集节点文档（排除 Episode）
                for node in self._nodes.values():
                    if "Episode" in node.labels:
                        continue
                    text = f"{node.name} {node.summary}"
                    if text.strip():
                        documents.append(text)
                        doc_ids.append(node.uuid)
                        doc_types.append("node")

                if documents:
                    self._tfidf_vectorizer = TfidfVectorizer(
                        max_features=10000,
                        analyzer='word',
                        ngram_range=(1, 2),
                    )
                    self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(documents)
                    self._tfidf_doc_ids = doc_ids
                    self._tfidf_doc_types = doc_types
                else:
                    self._tfidf_matrix = None
                    self._tfidf_vectorizer = None
                    self._tfidf_doc_ids = []
                    self._tfidf_doc_types = []

                self._tfidf_dirty = False
                logger.info(f"TF-IDF 索引已构建: {len(documents)} 文档")

            except ImportError:
                logger.warning("scikit-learn 未安装，搜索将使用关键词匹配")
                self._tfidf_dirty = False
            except Exception as e:
                logger.warning(f"构建 TF-IDF 索引失败: {e}")
                self._tfidf_dirty = False

    # ========== 图谱统计 ==========

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        entity_types = {}
        for node in self._nodes.values():
            for label in node.labels:
                if label not in ("Entity", "Node", "Episode"):
                    entity_types[label] = entity_types.get(label, 0) + 1

        relation_types = {}
        for edge in self._edges.values():
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1

        return {
            "graph_id": self.graph_id,
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }

    # ========== 持久化 ==========

    def _data_path(self) -> str:
        """数据文件路径"""
        return os.path.join(self._store_dir, f"{self.graph_id}.json")

    def _save(self):
        """保存图谱数据到 JSON 文件"""
        data = {
            "graph_id": self.graph_id,
            "name": self._name,
            "description": self._description,
            "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            "edges": {k: v.to_dict() for k, v in self._edges.items()},
            "ontology": {
                "entity_types": self._ontology.entity_types,
                "edge_types": self._ontology.edge_types,
            },
            "saved_at": datetime.now().isoformat(),
        }
        try:
            # 原子写入：避免 graph 构建过程中前端读到半截 JSON
            atomic_write_json(self._data_path(), data)
        except Exception as e:
            logger.error(f"保存图谱失败: {e}")

    def _load_if_exists(self):
        """如果存在持久化数据则加载"""
        path = self._data_path()
        if not os.path.exists(path):
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._name = data.get("name", "")
            self._description = data.get("description", "")

            # 加载节点
            for node_uuid, node_data in data.get("nodes", {}).items():
                node = NodeData(**node_data)
                self._nodes[node_uuid] = node
                self._graph.add_node(node_uuid, name=node.name, labels=node.labels)

            # 加载边
            for edge_uuid, edge_data in data.get("edges", {}).items():
                edge = EdgeData(**edge_data)
                self._edges[edge_uuid] = edge
                self._graph.add_edge(
                    edge.source_node_uuid, edge.target_node_uuid,
                    uuid=edge_uuid, name=edge.name
                )

            # 加载本体
            onto = data.get("ontology", {})
            self._ontology.entity_types = onto.get("entity_types", {})
            self._ontology.edge_types = onto.get("edge_types", {})

            self._tfidf_dirty = True
            # 优化（清理噪音）：从 INFO 降为 DEBUG
            # 旧实现：每次 GraphStore(graph_id) 实例化（高频操作）都打印一条，
            # API 端点每次调用都创建新实例 → 一天 1448 条
            # 关键信息（节点/边数）改在初始化时一次性 INFO（仅当非空）
            # 业务语义不变：图谱本身已加载
            logger.debug(f"加载图谱: {self.graph_id}, "
                        f"{len(self._nodes)} 节点, {len(self._edges)} 边")

        except Exception as e:
            logger.warning(f"加载图谱数据失败: {e}")

    # ========== 静态方法：列出所有图谱 ==========

    @classmethod
    def list_graphs(cls) -> List[Dict[str, str]]:
        """列出所有已保存的图谱"""
        graphs = []
        store_dir = cls._store_dir
        if os.path.exists(store_dir):
            for fname in os.listdir(store_dir):
                if fname.endswith('.json'):
                    graph_id = fname[:-5]
                    path = os.path.join(store_dir, fname)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        graphs.append({
                            "graph_id": graph_id,
                            "name": data.get("name", ""),
                            "node_count": len(data.get("nodes", {})),
                            "edge_count": len(data.get("edges", {})),
                        })
                    except Exception:
                        pass
        return graphs
