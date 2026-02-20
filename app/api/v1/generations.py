"""
Generations Router

Endpoints for generating phishing messages via LLM and listing results.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.scenario import Scenario
from app.models.generation import Generation
from app.schemas.generation import (
    GenerationCreate,
    GenerationResponse,
    GenerationListResponse,
)
from app.services.audit import log_action

router = APIRouter()


@router.post("/", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
def create_generation(
    data: GenerationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a phishing message using the LLM.

    This is a placeholder — the full LLM integration will be
    implemented in Phase 2, Sprint 2.4.
    """
    # Verify scenario ownership
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == data.scenario_id, Scenario.user_id == current_user.id)
        .first()
    )
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found or access denied",
        )

    # TODO: Phase 2 — integrate LLM service
    # For now, create a stub generation record
    generation = Generation(
        scenario_id=data.scenario_id,
        template_id=data.template_id,
        input_parameters={
            "temperature": data.temperature,
            "max_tokens": data.max_tokens,
            "model_variant": data.model_variant,
        },
        generated_subject="[Placeholder] Phishing Subject",
        generated_text="[Placeholder] This is a stub generation. LLM integration pending (Phase 2, Sprint 2.4).",
        model_used=data.model_variant,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)

    log_action(
        db,
        current_user.id,
        "generation.create",
        "generation",
        generation.id,
        details={"scenario_id": str(data.scenario_id), "model": data.model_variant},
    )
    return generation


@router.get("/", response_model=GenerationListResponse)
def list_generations(
    scenario_id: UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List generations for the current user (optionally filtered by scenario)."""
    query = (
        db.query(Generation)
        .join(Scenario)
        .filter(Scenario.user_id == current_user.id)
    )

    if scenario_id:
        query = query.filter(Generation.scenario_id == scenario_id)

    total = query.count()
    items = (
        query.order_by(Generation.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return GenerationListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{generation_id}", response_model=GenerationResponse)
def get_generation(
    generation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific generation."""
    generation = (
        db.query(Generation)
        .join(Scenario)
        .filter(Generation.id == generation_id, Scenario.user_id == current_user.id)
        .first()
    )
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found",
        )
    return generation
