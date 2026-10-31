"""Pydantic base classes for graph nodes and links, stored through services.graph_store."""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel

N = TypeVar("N", bound="GraphNode")


class GraphNode(BaseModel):
    """A node: its label and the field that identifies it are class settings."""

    __primarylabel__: ClassVar[str]
    __primaryproperty__: ClassVar[str] = "id"

    @property
    def node_key(self) -> tuple[str, str]:
        return self.__primarylabel__, str(getattr(self, self.__primaryproperty__))

    def merge(self, conn: Any = None) -> None:
        """Create the node or update it with every field of this model."""
        from services import graph_store

        graph_store.merge_node(*self.node_key, self.model_dump(mode="json"), conn)

    # The old Neo4j models had a separate create(); in Postgres both are an upsert
    create = merge

    @classmethod
    def match(cls: type[N], value: Any, conn: Any = None) -> N | None:
        from services import graph_store

        props = graph_store.get_node(cls.__primarylabel__, str(value), conn)
        return cls.model_validate(props) if props is not None else None


class GraphRelationship(BaseModel):
    """A link from `source` to `target`; any other fields are stored on the link."""

    __relationshiptype__: ClassVar[str]

    source: GraphNode
    target: GraphNode

    def merge(self, conn: Any = None) -> bool:
        from services import graph_store

        props = self.model_dump(mode="json", exclude={"source", "target"})
        return graph_store.merge_edge(self.__relationshiptype__, self.source.node_key, self.target.node_key, props, conn)
