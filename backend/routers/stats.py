from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, get_current_user
from schemas.stats import OverviewStats
from services import stats_service

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewStats)
def overview(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    return OverviewStats(**stats_service.get_overview(db))
