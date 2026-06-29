"""
实体读取与过滤服务
从本地 GraphStore 读取节点，筛选出符合预定义实体类型的节点
（替代原 Zep Cloud 版本）
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from .graph_store import GraphStore

logger = get_logger('mirofish.entity_reader')


@dataclass
class EntityNode:
    """实体节点数据结构"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """获取实体类型（排除默认的Entity标签）"""
        for label in self.labels:
            if label not in ("Entity", "Node", "Episode"):
                return label
        return None


@dataclass
class FilteredEntities:
    """过滤后的实体集合"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    实体读取与过滤服务

    主要功能：
    1. 从图谱读取所有节点
    2. 筛选出符合预定义实体类型的节点
    3. 获取每个实体的相关边和关联节点信息
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key 参数保留以兼容调用方，但不再需要
        pass

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """获取图谱的所有节点"""
        logger.info(f"获取图谱 {graph_id} 的所有节点...")
        store = GraphStore(graph_id)
        nodes = store.get_all_nodes()

        nodes_data = [
            {
                "uuid": n.uuid,
                "name": n.name,
                "labels": n.labels,
                "summary": n.summary,
                "attributes": n.attributes,
            }
            for n in nodes
            if "Episode" not in n.labels
        ]

        logger.info(f"共获取 {len(nodes_data)} 个节点")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """获取图谱的所有边"""
        logger.info(f"获取图谱 {graph_id} 的所有边...")
        store = GraphStore(graph_id)
        edges = store.get_all_edges()

        edges_data = [
            {
                "uuid": e.uuid,
                "name": e.name,
                "fact": e.fact,
                "source_node_uuid": e.source_node_uuid,
                "target_node_uuid": e.target_node_uuid,
                "attributes": e.attributes,
            }
            for e in edges
        ]

        logger.info(f"共获取 {len(edges_data)} 条边")
        return edges_data

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """获取指定节点的所有相关边"""
        try:
            # 需要遍历所有图谱找到包含该节点的图
            # 由于 GraphStore 是按 graph_id 隔离的，这里需要一个 graph_id
            # 实际使用时调用方会通过 filter_defined_entities 传入 graph_id
            # 这里提供一个简化实现
            logger.warning(f"get_node_edges 需要 graph_id 参数，请使用 filter_defined_entities")
            return []
        except Exception as e:
            logger.warning(f"获取节点 {node_uuid} 的边失败: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """筛选出符合预定义实体类型的节点"""
        logger.info(f"开始筛选图谱 {graph_id} 的实体...")

        store = GraphStore(graph_id)

        # 获取所有节点（排除 Episode）
        all_nodes = [n for n in store.get_all_nodes() if "Episode" not in n.labels]
        total_count = len(all_nodes)

        # 获取所有边
        all_edges = store.get_all_edges() if enrich_with_edges else []

        # 构建节点映射
        node_map = {n.uuid: n for n in all_nodes}

        # 筛选
        filtered_entities = []
        entity_types_found = set()

        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ("Entity", "Node", "Episode")]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node.uuid,
                name=node.name,
                labels=node.labels,
                summary=node.summary,
                attributes=node.attributes,
            )

            # 获取相关边和节点
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()

                for edge in all_edges:
                    if edge.source_node_uuid == node.uuid:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge.name,
                            "fact": edge.fact,
                            "target_node_uuid": edge.target_node_uuid,
                        })
                        related_node_uuids.add(edge.target_node_uuid)
                    elif edge.target_node_uuid == node.uuid:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge.name,
                            "fact": edge.fact,
                            "source_node_uuid": edge.source_node_uuid,
                        })
                        related_node_uuids.add(edge.source_node_uuid)

                entity.related_edges = related_edges

                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node.uuid,
                            "name": related_node.name,
                            "labels": related_node.labels,
                            "summary": related_node.summary,
                        })
                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"筛选完成: 总节点 {total_count}, 符合条件 {len(filtered_entities)}, "
                   f"实体类型: {entity_types_found}")

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """获取单个实体及其完整上下文"""
        try:
            store = GraphStore(graph_id)
            node = store.get_node(entity_uuid)

            if not node or "Episode" in node.labels:
                return None

            # 获取边和关联节点
            edges = store.get_node_edges(entity_uuid)
            all_nodes = store.get_all_nodes()
            node_map = {n.uuid: n for n in all_nodes}

            related_edges = []
            related_node_uuids = set()

            for edge in edges:
                if edge.source_node_uuid == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge.name,
                        "fact": edge.fact,
                        "target_node_uuid": edge.target_node_uuid,
                    })
                    related_node_uuids.add(edge.target_node_uuid)
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                    })
                    related_node_uuids.add(edge.source_node_uuid)

            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node.uuid,
                        "name": related_node.name,
                        "labels": related_node.labels,
                        "summary": related_node.summary,
                    })

            return EntityNode(
                uuid=node.uuid,
                name=node.name,
                labels=node.labels,
                summary=node.summary,
                attributes=node.attributes,
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"获取实体 {entity_uuid} 失败: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """获取指定类型的所有实体"""
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
