from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import EmailStr, Field

from models.graph_model import GraphNode


class UserNode(GraphNode):
    __primarylabel__: ClassVar[str] = "User"
    __primaryproperty__: ClassVar[str] = "email"

    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    password: str
    fullname: str
