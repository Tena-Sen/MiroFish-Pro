"""兼容性包装模块。

此模块原来用于 Zep Cloud 的分页读取，
现已切换为本地 GraphStore，不再需要分页逻辑。
保留此文件以避免导入错误。
"""

from __future__ import annotations
from typing import Any


def fetch_all_nodes(client: Any, graph_id: str, **kwargs: Any) -> list[Any]:
    """
    兼容性函数 - 已弃用
    请直接使用 GraphStore.get_all_nodes()
    """
    from ..services.graph_store import GraphStore
    store = GraphStore(graph_id)
    return store.get_all_nodes()


def fetch_all_edges(client: Any, graph_id: str, **kwargs: Any) -> list[Any]:
    """
    兼容性函数 - 已弃用
    请直接使用 GraphStore.get_all_edges()
    """
    from ..services.graph_store import GraphStore
    store = GraphStore(graph_id)
    return store.get_all_edges()
