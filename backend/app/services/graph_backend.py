"""
图谱后端适配层。

统一抽象两类后端：

- ``local``  (默认): ``GraphStore`` (NetworkX + TF-IDF, 进程内 JSON 持久化)
- ``zep``: Zep Cloud Standalone Graph (zep-cloud SDK, 第三方云端服务)

上层调用方（``GraphBuilderService``、``ZepEntityReader``、
``ZepToolsService``、``OasisProfileGenerator``、``ZepGraphMemoryUpdater``、
graph API 等）不再直接 ``import graph_store.GraphStore``，
而是通过本模块暴露的统一接口获取后端实例。

约定接口（两个后端都必须实现）::

    create_graph(name, description) -> str                       # 返回 graph_id
    set_ontology(graph_id, entity_types, edge_types) -> None
    add_text_batches(graph_id, texts, ontology=None, ...) -> List[str]
    wait_for_episodes(graph_id, episode_uuids, timeout=...) -> None
    get_all_nodes(graph_id) -> List[NodeData]
    get_all_edges(graph_id) -> List[EdgeData]
    get_node(graph_id, node_uuid) -> Optional[NodeData]
    get_node_edges(graph_id, node_uuid) -> List[EdgeData]
    search(graph_id, query, limit, scope) -> Dict[str, Any]
    get_statistics(graph_id) -> Dict[str, Any]
    add_single_episode(graph_id, text, episode_type) -> str
    delete_graph(graph_id) -> None

后端选择由 ``Config.GRAPH_BACKEND`` 控制（``local`` 或 ``zep``）。
``zep`` 后端需要安装可选依赖 ``zep-cloud``；未安装时仅在使用时才会抛错，
不会影响默认 ``local`` 模式的导入。
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger
from .graph_store import EdgeData, GraphStore, NodeData

logger = get_logger("mirofish.graph_backend")


# ===========================================================================
# 工厂：get_graph_backend()
# ===========================================================================

_GRAPH_BACKEND_REGISTRY: Dict[str, "GraphBackend"] = {}


def get_graph_backend(graph_id: Optional[str] = None) -> "GraphBackend":
    """按配置返回后端实例。

    Args:
        graph_id: 图谱 ID。``local`` 后端必须提供；``zep`` 后端可选（延迟创建）。

    Returns:
        实现统一接口的 ``GraphBackend`` 实例。
    """
    backend_kind = (Config.GRAPH_BACKEND or "local").lower().strip()

    if backend_kind == "local":
        if not graph_id:
            raise ValueError("local 后端必须提供 graph_id")
        return LocalGraphBackend(graph_id)

    if backend_kind == "zep":
        if graph_id:
            return ZepGraphBackend.for_graph(graph_id)
        return ZepGraphBackend.instance()

    raise ValueError(
        f"未知的 GRAPH_BACKEND: {backend_kind!r}，仅支持 'local' 或 'zep'"
    )


# 向后兼容：旧调用方使用 ``get_graph_store`` 拿 GraphStore 实例。
# local 后端会真正返回 GraphStore 实例；zep 后端则返回一个轻量适配对象，
# 暴露出 GraphStore 上层需要的同名方法（get_all_nodes / get_all_edges / search / …）。
def get_graph_store(graph_id: str):
    """兼容旧调用方：返回带 GraphStore 接口的适配对象。"""
    backend = get_graph_backend(graph_id)
    if isinstance(backend, LocalGraphBackend):
        return backend.store
    # zep 后端：直接返回 ZepGraphBackend，其接口覆盖 GraphStore 调用点
    return backend


# ===========================================================================
# 统一接口
# ===========================================================================

class GraphBackend:
    """图谱后端抽象基类。

    所有方法必须实现。子类的 ``graph_id`` 实例属性应为字符串。
    """

    backend_name: str = "base"

    def __init__(self, graph_id: str):
        self.graph_id = graph_id

    # ------- 生命周期 -------
    def create_graph(self, name: str = "MiroFish Graph", description: str = "") -> str:
        raise NotImplementedError

    def delete_graph(self, graph_id: Optional[str] = None) -> None:
        raise NotImplementedError

    # ------- 本体 -------
    def set_ontology(
        self,
        entity_types: Dict[str, Any],
        edge_types: Dict[str, Any],
    ) -> None:
        raise NotImplementedError

    # ------- 写入 -------
    def add_text_batches(
        self,
        texts: List[str],
        ontology: Optional[Dict[str, Any]] = None,
        batch_size: int = 3,
        progress_callback=None,
        chunk_parallel: int = 1,
    ) -> List[str]:
        """把文本分批写入图谱并触发实体抽取。

        对于 local 后端，会在本地用 LLM 抽取实体/关系；
        对于 zep 后端，仅负责 add_batch + wait_for_episodes，
        实体抽取交给 Zep 服务端完成。
        """
        raise NotImplementedError

    def add_single_episode(self, text: str, episode_type: str = "text") -> str:
        raise NotImplementedError

    def wait_for_episodes(
        self,
        episode_uuids: List[str],
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> None:
        """等待 episode 被服务端处理完成。仅对 zep 后端有意义，local 直接返回。"""
        return None

    # ------- 读取 -------
    def get_all_nodes(self) -> List[NodeData]:
        raise NotImplementedError

    def get_all_edges(self) -> List[EdgeData]:
        raise NotImplementedError

    def get_node(self, node_uuid: str) -> Optional[NodeData]:
        raise NotImplementedError

    def get_node_edges(self, node_uuid: str) -> List[EdgeData]:
        raise NotImplementedError

    def search(self, query: str, limit: int = 10, scope: str = "edges") -> Dict[str, Any]:
        raise NotImplementedError

    def get_statistics(self) -> Dict[str, Any]:
        raise NotImplementedError


# ===========================================================================
# Local 后端
# ===========================================================================

class LocalGraphBackend(GraphBackend):
    """直接包装 ``GraphStore`` 的本地后端。

    ``add_text_batches`` 会在每个 batch 之后调用本地 LLM 抽取实体/关系，
    行为与历史实现完全一致。
    """

    backend_name = "local"

    def __init__(self, graph_id: str):
        super().__init__(graph_id)
        self.store = GraphStore(graph_id)

    # ------- 生命周期 -------
    def create_graph(self, name: str = "MiroFish Graph", description: str = "") -> str:
        self.store.create(name=name, description=description)
        return self.store.graph_id

    def delete_graph(self, graph_id: Optional[str] = None) -> None:
        target_id = graph_id or self.graph_id
        GraphStore(target_id).delete()

    # ------- 本体 -------
    def set_ontology(
        self,
        entity_types: Dict[str, Any],
        edge_types: Dict[str, Any],
    ) -> None:
        self.store.set_ontology(
            entity_types=entity_types,
            edge_types=edge_types,
        )

    # ------- 写入 -------
    def add_text_batches(
        self,
        texts: List[str],
        ontology: Optional[Dict[str, Any]] = None,
        batch_size: int = 3,
        progress_callback=None,
        chunk_parallel: int = 1,
    ) -> List[str]:
        # 延迟导入，避免循环引用
        from .graph_builder import GraphBuilderService

        builder = GraphBuilderService()
        return builder.add_text_batches(
            graph_id=self.graph_id,
            chunks=texts,
            ontology=ontology or {"entity_types": [], "edge_types": []},
            batch_size=batch_size,
            progress_callback=progress_callback,
            chunk_parallel=chunk_parallel,
        )

    def add_single_episode(self, text: str, episode_type: str = "text") -> str:
        return self.store.add_single_episode(text=text, episode_type=episode_type)

    def wait_for_episodes(self, episode_uuids: List[str], timeout: float = 60.0, poll_interval: float = 2.0) -> None:
        # 本地存储同步处理，无需等待
        return None

    # ------- 读取 -------
    def get_all_nodes(self) -> List[NodeData]:
        return self.store.get_all_nodes()

    def get_all_edges(self) -> List[EdgeData]:
        return self.store.get_all_edges()

    def get_node(self, node_uuid: str) -> Optional[NodeData]:
        return self.store.get_node(node_uuid)

    def get_node_edges(self, node_uuid: str) -> List[EdgeData]:
        return self.store.get_node_edges(node_uuid)

    def search(self, query: str, limit: int = 10, scope: str = "edges") -> Dict[str, Any]:
        return self.store.search(query=query, limit=limit, scope=scope)

    def get_statistics(self) -> Dict[str, Any]:
        return self.store.get_statistics()


# ===========================================================================
# Zep 后端
# ===========================================================================

class ZepGraphBackend(GraphBackend):
    """Zep Cloud Standalone Graph 后端。

    - 实体抽取交给 Zep 服务端：仅做 ``add_batch`` + 轮询 ``episode.get``。
    - 不在本地执行 LLM 实体抽取。
    - 读取接口把 zep-cloud 对象转换成 ``NodeData`` / ``EdgeData`` 字典，
      与 ``GraphStore`` 调用点的签名兼容。
    """

    backend_name = "zep"

    _instance: Optional["ZepGraphBackend"] = None
    _instance_lock_owner: Optional[str] = None  # 用于进程内单例（debug 用）

    # ----------- 工厂 -----------

    @classmethod
    def instance(cls) -> "ZepGraphBackend":
        """创建或返回延迟初始化的实例（graph_id 后续通过 create_graph 分配）。"""
        if cls._instance is None:
            cls._instance = cls(graph_id="")
        return cls._instance

    @classmethod
    def for_graph(cls, graph_id: str) -> "ZepGraphBackend":
        """为指定 graph_id 创建一个新实例（不挂单例）。"""
        return cls(graph_id=graph_id)

    # ----------- 初始化 -----------

    def __init__(self, graph_id: str):
        super().__init__(graph_id)
        # 关键：不要在模块顶部 import zep_cloud，否则 local 模式也会失败。
        try:
            from zep_cloud.client import Zep  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "GRAPH_BACKEND=zep 时需要安装可选依赖 zep-cloud："
                "uv pip install zep-cloud 或 pip install zep-cloud"
            ) from exc

        if not Config.ZEP_API_KEY:
            raise ValueError("GRAPH_BACKEND=zep 时必须配置 ZEP_API_KEY")

        self.client = Zep(api_key=Config.ZEP_API_KEY)

    # ----------- 内部辅助 -----------

    @staticmethod
    def _node_to_data(node: Any) -> NodeData:
        return NodeData(
            uuid=getattr(node, "uuid_", None) or getattr(node, "uuid", ""),
            name=getattr(node, "name", "") or "",
            labels=getattr(node, "labels", None) or [],
            summary=getattr(node, "summary", "") or "",
            attributes=getattr(node, "attributes", None) or {},
        )

    @staticmethod
    def _edge_to_data(edge: Any) -> EdgeData:
        return EdgeData(
            uuid=getattr(edge, "uuid_", None) or getattr(edge, "uuid", ""),
            name=getattr(edge, "name", "") or "",
            fact=getattr(edge, "fact", "") or "",
            source_node_uuid=getattr(edge, "source_node_uuid", "") or "",
            target_node_uuid=getattr(edge, "target_node_uuid", "") or "",
            attributes=getattr(edge, "attributes", None) or {},
            created_at=getattr(edge, "created_at", None) or "",
            valid_at=getattr(edge, "valid_at", None),
            invalid_at=getattr(edge, "invalid_at", None),
            expired_at=getattr(edge, "expired_at", None),
        )

    def _require_graph_id(self) -> str:
        if not self.graph_id:
            raise ValueError("Zep 后端尚未创建图谱，请先调用 create_graph()")
        return self.graph_id

    # ----------- 生命周期 -----------

    def create_graph(self, name: str = "MiroFish Graph", description: str = "") -> str:
        # 先固定 graph_id，避免 SDK 返回对象不带 graph_id 时丢失实际创建的 ID。
        new_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        try:
            result = self.client.graph.create(
                graph_id=new_id,
                name=name,
                description=description or "",
            )
        except TypeError:
            # 兼容没有 graph_id 参数的旧版本
            result = self.client.graph.create(name=name, description=description or "")
            new_id = getattr(result, "graph_id", None) or new_id
        # Zep SDK 返回对象没有 graph_id 时，优先使用请求时传入的固定 ID。
        requested_id = new_id
        if result is not None:
            new_id = (
                getattr(result, "graph_id", None)
                or getattr(result, "uuid_", None)
                or getattr(result, "uuid", None)
                or requested_id
            )
        else:
            new_id = requested_id

        self.graph_id = new_id
        logger.info(f"[zep] 创建图谱: {new_id} ({name})")
        return new_id

    def delete_graph(self, graph_id: Optional[str] = None) -> None:
        target_id = graph_id or self.graph_id
        if not target_id:
            return
        try:
            self.client.graph.delete(graph_id=target_id)
            logger.info(f"[zep] 删除图谱: {target_id}")
        except Exception as e:
            logger.warning(f"[zep] 删除图谱失败（已忽略）: {e}")

    # ----------- 本体 -----------

    def set_ontology(
        self,
        entity_types: Dict[str, Any],
        edge_types: Dict[str, Any],
    ) -> None:
        graph_id = self._require_graph_id()

        # 按历史 Zep SDK 约定，把 JSON 本体转换为 Pydantic 模型类。
        import warnings
        from typing import Optional as _Optional
        from pydantic import Field
        from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel
        from zep_cloud import EntityEdgeSourceTarget

        warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
        reserved_names = {"uuid", "name", "group_id", "name_embedding", "summary", "created_at"}

        def safe_attr_name(attr_name: str) -> str:
            return f"entity_{attr_name}" if attr_name.lower() in reserved_names else attr_name

        zep_entity_types = {}
        for name, info in (entity_types or {}).items():
            if isinstance(info, type) and issubclass(info, EntityModel):
                zep_entity_types[name] = info
                continue
            info = info if isinstance(info, dict) else {}
            attrs = {"__doc__": info.get("description", f"A {name} entity.")}
            annotations = {}
            for attr_def in info.get("attributes", []):
                attr_name = safe_attr_name(attr_def.get("name", "attribute"))
                attrs[attr_name] = Field(
                    description=attr_def.get("description", attr_name),
                    default=None,
                )
                annotations[attr_name] = _Optional[EntityText]
            attrs["__annotations__"] = annotations
            zep_entity_types[name] = type(name, (EntityModel,), attrs)

        zep_edge_types = {}
        for name, info in (edge_types or {}).items():
            if isinstance(info, tuple) and len(info) == 2:
                zep_edge_types[name] = info
                continue
            info = info if isinstance(info, dict) else {}
            attrs = {"__doc__": info.get("description", f"A {name} relationship.")}
            annotations = {}
            for attr_def in info.get("attributes", []):
                attr_name = safe_attr_name(attr_def.get("name", "attribute"))
                attrs[attr_name] = Field(
                    description=attr_def.get("description", attr_name),
                    default=None,
                )
                annotations[attr_name] = _Optional[str]
            attrs["__annotations__"] = annotations
            edge_class = type("".join(part.capitalize() for part in name.split("_")), (EdgeModel,), attrs)
            source_targets = [
                EntityEdgeSourceTarget(
                    source=pair.get("source", "Entity"),
                    target=pair.get("target", "Entity"),
                )
                for pair in info.get("source_targets", [])
            ]
            if source_targets:
                zep_edge_types[name] = (edge_class, source_targets)

        try:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=zep_entity_types or None,
                edges=zep_edge_types or None,
            )
        except TypeError:
            self.client.graph.set_ontology(
                entities=zep_entity_types or None,
                edges=zep_edge_types or None,
            )
        logger.info(f"[zep] 设置本体: graph_id={graph_id}, "
                    f"{len(zep_entity_types)} 实体类型, {len(zep_edge_types)} 关系类型")

    # ----------- 写入 -----------

    def add_text_batches(
        self,
        texts: List[str],
        ontology: Optional[Dict[str, Any]] = None,
        batch_size: int = 3,
        progress_callback=None,
        chunk_parallel: int = 1,
    ) -> List[str]:
        """Zep 模式：直接 add_batch；实体抽取由 Zep 服务端异步完成。

        不会执行本地 LLM 抽取。``chunk_parallel`` 在 Zep 后端被忽略
        （API 调用本身是网络请求，多并发反而容易触发限流）。
        """
        from zep_cloud import EpisodeData  # type: ignore

        graph_id = self._require_graph_id()
        episode_uuids: List[str] = []

        total = len(texts)
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            episodes = [EpisodeData(data=t, type="text") for t in batch]

            if progress_callback:
                try:
                    progress_callback(
                        f"[zep] 提交第 {batch_num}/{total_batches} 批 ({len(batch)} chunks)",
                        (i + len(batch)) / max(total, 1),
                    )
                except Exception:
                    pass

            result = self.client.graph.add_batch(
                graph_id=graph_id,
                episodes=episodes,
            )

            for ep in (result or []):
                ep_uuid = getattr(ep, "uuid_", None) or getattr(ep, "uuid", None) or ""
                if ep_uuid:
                    episode_uuids.append(ep_uuid)

        logger.info(f"[zep] add_batch 完成: graph_id={graph_id}, episodes={len(episode_uuids)}")
        return episode_uuids

    def wait_for_episodes(
        self,
        episode_uuids: List[str],
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> None:
        """轮询 graph.episode.get 直到 processed=True 或超时。

        Zep 后端实体抽取是异步的；调用方需要等服务端处理完成
        （节点/边才会在 graph.search / node.get_by_graph_id 中可见）。
        """
        if not episode_uuids:
            return

        deadline = time.time() + max(timeout, 1.0)
        pending = list(episode_uuids)

        while pending and time.time() < deadline:
            still_pending: List[str] = []
            for ep_uuid in pending:
                try:
                    ep = self.client.graph.episode.get(uuid_=ep_uuid)
                except Exception as e:
                    logger.debug(f"[zep] graph.episode.get({ep_uuid}) 失败（忽略）: {e}")
                    still_pending.append(ep_uuid)
                    continue

                processed = bool(
                    getattr(ep, "processed", False)
                    or getattr(ep, "status", "") in ("processed", "completed")
                )
                if not processed:
                    still_pending.append(ep_uuid)

            if not still_pending:
                logger.info(f"[zep] 所有 episode 处理完成: {len(episode_uuids)} 条")
                return

            pending = still_pending
            time.sleep(max(poll_interval, 0.1))

        if pending:
            logger.warning(f"[zep] episode 处理超时: 未完成 {len(pending)} 条")

    def add_single_episode(self, text: str, episode_type: str = "text") -> str:
        from zep_cloud import EpisodeData  # type: ignore

        graph_id = self._require_graph_id()
        result = self.client.graph.add_batch(
            graph_id=graph_id,
            episodes=[EpisodeData(data=text, type=episode_type)],
        )
        if result:
            ep = result[0]
            return getattr(ep, "uuid_", None) or getattr(ep, "uuid", "")
        return ""

    # ----------- 读取 -----------

    def get_all_nodes(self) -> List[NodeData]:
        graph_id = self._require_graph_id()
        nodes = self.client.graph.node.get_by_graph_id(graph_id=graph_id)
        return [self._node_to_data(n) for n in (nodes or [])]

    def get_all_edges(self) -> List[EdgeData]:
        graph_id = self._require_graph_id()
        edges = self.client.graph.edge.get_by_graph_id(graph_id=graph_id)
        return [self._edge_to_data(e) for e in (edges or [])]

    def get_node(self, node_uuid: str) -> Optional[NodeData]:
        try:
            node = self.client.graph.node.get(uuid_=node_uuid)
        except Exception:
            return None
        return self._node_to_data(node) if node else None

    def get_node_edges(self, node_uuid: str) -> List[EdgeData]:
        try:
            edges = self.client.graph.node.get_entity_edges(node_uuid=node_uuid)
        except Exception:
            return []
        return [self._edge_to_data(e) for e in (edges or [])]

    def search(self, query: str, limit: int = 10, scope: str = "edges") -> Dict[str, Any]:
        graph_id = self._require_graph_id()
        try:
            results = self.client.graph.search(
                graph_id=graph_id,
                query=query,
                limit=limit,
                scope=scope,
                reranker="cross_encoder",
            )
        except TypeError:
            results = self.client.graph.search(
                graph_id=graph_id,
                query=query,
                limit=limit,
                scope=scope,
            )

        edges: List[Dict[str, Any]] = []
        nodes: List[Dict[str, Any]] = []
        for edge in getattr(results, "edges", None) or []:
            edges.append(self._edge_to_data(edge).to_dict())
        for node in getattr(results, "nodes", None) or []:
            nodes.append(self._node_to_data(node).to_dict())
        return {"edges": edges, "nodes": nodes}

    def get_statistics(self) -> Dict[str, Any]:
        graph_id = self._require_graph_id()
        nodes = [n for n in self.get_all_nodes() if "Episode" not in n.labels]
        edges = self.get_all_edges()

        entity_types: Dict[str, int] = {}
        relation_types: Dict[str, int] = {}
        for node in nodes:
            for label in node.labels:
                if label not in ("Entity", "Node", "Episode"):
                    entity_types[label] = entity_types.get(label, 0) + 1
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1

        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }
