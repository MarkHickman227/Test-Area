from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_repository
from app.models import CvCreateRequest, CvRecord
from app.services.cv_parser import parse_cv_profile

router = APIRouter(prefix="/api")

Repo = Annotated[Any, Depends(get_repository)]


@router.get("/cvs", response_model=list[CvRecord])
async def list_cvs(repository: Repo) -> list[CvRecord]:
    return await repository.list_cvs()


@router.post("/cvs", response_model=CvRecord, status_code=status.HTTP_201_CREATED)
async def create_cv(request: CvCreateRequest, repository: Repo) -> CvRecord:
    payload = request.model_dump(mode="json")
    payload["parsed_profile"] = parse_cv_profile(payload["raw_text"])
    return await repository.create_cv(payload)


@router.delete("/cvs/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(cv_id: UUID, repository: Repo) -> None:
    await repository.delete_cv(cv_id)
