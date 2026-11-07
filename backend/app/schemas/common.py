from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](ApiModel):
    items: list[T]
    next_cursor: str | None = None
