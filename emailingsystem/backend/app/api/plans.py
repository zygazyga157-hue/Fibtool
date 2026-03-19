"""
Plans endpoints for listing available products.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.plan import Plan
from app.schemas import PlanResponse

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=List[PlanResponse])
async def list_plans(db: Session = Depends(get_db)):
    """List all available plans."""
    plans = db.query(Plan).all()
    return plans
