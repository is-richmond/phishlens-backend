"""
Scenarios Router

CRUD endpoints for phishing scenario management with filtering, search,
and persona preset support.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, get_client_ip
from app.models.user import User
from app.models.scenario import Scenario
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioListResponse,
    PretextCategory,
    CommunicationChannel,
)
from app.services.audit import log_action
from app.services.prompt_service import prompt_service

router = APIRouter()


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    data: ScenarioCreate,
    request: Request,
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

    log_action(
        db,
        current_user.id,
        "scenario.create",
        "scenario",
        scenario.id,
        details={"category": data.pretext_category.value, "channel": data.communication_channel.value},
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return scenario


@router.get("/presets/personas")
def list_persona_presets(
    current_user: User = Depends(get_current_user),
):
    """List available target persona presets with detailed descriptions.

    Returns predefined personas that can be used as target_role values
    when creating scenarios, along with suggested department and context.
    """
    presets = []
    for role, desc in prompt_service.TARGET_PERSONAS.items():
        presets.append({
            "target_role": role,
            "description": desc,
            "suggested_department": _suggest_department(role),
        })
    return presets


@router.get("/presets/categories")
def list_pretext_categories(
    current_user: User = Depends(get_current_user),
):
    """List all available pretext categories with descriptions and tactics.

    Returns detailed information about each phishing attack category
    including common tactics used.
    """
    categories = []
    for cat, desc in prompt_service.PRETEXT_DESCRIPTIONS.items():
        categories.append({
            "category": cat,
            "description": desc,
            "label": cat.replace("_", " ").title(),
        })
    return categories


@router.get("/", response_model=ScenarioListResponse)
def list_scenarios(
    category: PretextCategory | None = None,
    channel: CommunicationChannel | None = None,
    search: str | None = None,
    urgency_min: int | None = Query(None, ge=1, le=5),
    urgency_max: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List scenarios owned by the current user with optional filtering."""
    query = db.query(Scenario).filter(Scenario.user_id == current_user.id)

    # Filter by pretext category
    if category:
        query = query.filter(Scenario.pretext_category == category.value)

    # Filter by communication channel
    if channel:
        query = query.filter(Scenario.communication_channel == channel.value)

    # Filter by urgency range
    if urgency_min is not None:
        query = query.filter(Scenario.urgency_level >= urgency_min)
    if urgency_max is not None:
        query = query.filter(Scenario.urgency_level <= urgency_max)

    # Full-text search across title, description, target_role, target_department
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Scenario.title.ilike(search_term),
                Scenario.description.ilike(search_term),
                Scenario.target_role.ilike(search_term),
                Scenario.target_department.ilike(search_term),
                Scenario.organization_context.ilike(search_term),
            )
        )

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
    request: Request,
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

    log_action(
        db,
        current_user.id,
        "scenario.update",
        "scenario",
        scenario.id,
        details={"updated_fields": list(update_data.keys())},
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: UUID,
    request: Request,
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

    log_action(
        db,
        current_user.id,
        "scenario.delete",
        "scenario",
        scenario.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    db.delete(scenario)
    db.commit()


def _suggest_department(role: str) -> str:
    """Suggest a department based on a target role."""
    role_lower = role.lower()
    dept_map = {
        "hr manager": "Human Resources",
        "software engineer": "Engineering / IT",
        "c-level executive": "Executive Management",
        "finance manager": "Finance / Accounting",
        "it administrator": "Information Technology",
        "receptionist": "Front Office / Administration",
        "sales representative": "Sales / Business Development",
    }
    return dept_map.get(role_lower, "General")
