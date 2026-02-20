"""
Scenarios Router

CRUD endpoints for phishing scenario management.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.scenario import Scenario
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioListResponse,
)
from app.services.audit import log_action

router = APIRouter()


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    data: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new phishing scenario."""
    scenario = Scenario(
        user_id=current_user.id,
        **data.model_dump(),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    log_action(db, current_user.id, "scenario.create", "scenario", scenario.id)
    return scenario


@router.get("/", response_model=ScenarioListResponse)
def list_scenarios(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List scenarios owned by the current user."""
    query = db.query(Scenario).filter(Scenario.user_id == current_user.id)
    total = query.count()
    items = (
        query.order_by(Scenario.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return ScenarioListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific scenario by ID."""
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: UUID,
    data: ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing scenario."""
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scenario, field, value)

    db.commit()
    db.refresh(scenario)

    log_action(db, current_user.id, "scenario.update", "scenario", scenario.id)
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a scenario."""
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    log_action(db, current_user.id, "scenario.delete", "scenario", scenario.id)

    db.delete(scenario)
    db.commit()
