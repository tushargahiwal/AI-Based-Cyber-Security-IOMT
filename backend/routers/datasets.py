from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, get_current_user, require_permission
from schemas.dataset import DatasetCreateRequest, DatasetOut, DatasetUpdateRequest
from services import audit_service, dataset_service

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    return [DatasetOut.model_validate(d) for d in dataset_service.list_datasets(db)]


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(
    body: DatasetCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    dataset = dataset_service.create_dataset(db, data=body.model_dump())
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_DATASET",
        entity_type="datasets",
        entity_id=dataset.id,
        new_value={"name": dataset.name, "version": dataset.version},
        ip_address=request.client.host if request.client else None,
    )
    return DatasetOut.model_validate(dataset)


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    dataset = dataset_service.get_dataset(db, dataset_id)
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dataset not found")
    return DatasetOut.model_validate(dataset)


@router.patch("/{dataset_id}", response_model=DatasetOut)
def update_dataset(
    dataset_id: int,
    body: DatasetUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    updates = body.model_dump(exclude_unset=True)
    dataset = dataset_service.update_dataset(db, dataset_id=dataset_id, updates=updates)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_DATASET",
        entity_type="datasets",
        entity_id=dataset_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return DatasetOut.model_validate(dataset)
