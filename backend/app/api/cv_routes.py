from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import CvCreateRequest, CvRecord
from app.services.repository import SupabaseRepository

router = APIRouter(prefix="/api")


def get_repository() -> SupabaseRepository:
    try:
        return SupabaseRepository()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/cvs", response_model=list[CvRecord])
async def list_cvs(
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> list[CvRecord]:
    return await repository.list_cvs()


@router.post("/cvs", response_model=CvRecord, status_code=status.HTTP_201_CREATED)
async def create_cv(
    request: CvCreateRequest,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> CvRecord:
    return await repository.create_cv(request.model_dump(mode="json"))


@router.delete("/cvs/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    cv_id: UUID,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> None:
    await repository.delete_cv(cv_id)
