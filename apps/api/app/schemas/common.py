from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class ListResponse(APIModel, Generic[T]):
    items: list[T]
    total: int


class ConsentPayload(APIModel):
    terms: str
    privacy: str
    content_policy: str
    age_policy: str
