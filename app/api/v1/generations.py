"""
Generations Router

Endpoints for generating phishing messages via LLM and listing/managing results.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, get_client_ip, require_terms_current
from app.models.user import User
from app.models.scenario import Scenario
from app.models.template import Template
from app.models.generation import Generation
from app.schemas.generation import (
    GenerationCreate,
    GenerationResponse,
    GenerationListResponse,
)
from app.services.audit import log_action
from app.services.generation_service import generation_service
from app.services.llm_service import llm_service, SUPPORTED_MODELS
from app.services.prompt_service import prompt_service
from app.services.abuse_detection import check_user_abuse
from app.core.logging import get_logger

logger = get_logger("generations_router")

router = APIRouter()


@router.post("", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
def create_generation(
    data: GenerationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_terms_current),
):
    """Generate a phishing message using the LLM pipeline.

    Requires current Terms of Use acceptance.  Checks for anomalous usage.

    1. Validates scenario ownership and optional template access
    2. Constructs prompt via three-tier pipeline
    3. Calls Gemini API to generate phishing message
    4. Evaluates realism via secondary LLM call
    5. Stores complete results with scores
    """
    # Abuse detection — flag anomalous generation volume
    check_user_abuse(
        db,
        current_user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

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

    # Verify template access (if provided)
    template = None
    if data.template_id:
        template = db.query(Template).filter(Template.id == data.template_id).first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        # Access check: predefined, public, or owned by user
        if (
            not template.is_predefined
            and not template.is_public
            and template.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this template",
            )

    # Validate model variant
    if data.model_variant not in SUPPORTED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model variant. Supported: {list(SUPPORTED_MODELS.keys())}",
        )

    # Run the generation pipeline
    try:
        generation = generation_service.generate(
            db=db,
            scenario=scenario,
            template=template,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            model_variant=data.model_variant,
        )
    except Exception as e:
        error_msg = str(e)
        logger.error("Generation pipeline failed", error=error_msg, scenario_id=str(data.scenario_id))

        # Surface a clean message for quota / rate-limit errors
        if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Gemini API quota exceeded. Your free-tier daily limit has been reached. "
                    "Please wait for the quota to reset or upgrade to a paid plan at "
                    "https://aistudio.google.com/"
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM generation failed: {error_msg}",
        )

    # Audit log with IP/UA tracking
    log_action(
        db,
        current_user.id,
        "generation.create",
        "generation",
        generation.id,
        details={
            "scenario_id": str(data.scenario_id),
            "template_id": str(data.template_id) if data.template_id else None,
            "model": data.model_variant,
            "temperature": data.temperature,
            "overall_score": float(generation.overall_score) if generation.overall_score else None,
        },
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return generation


@router.post("/{generation_id}/re-evaluate", response_model=GenerationResponse)
def re_evaluate_generation(
    generation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run the realism evaluation on an existing generation.

    Useful when evaluation failed or returned default scores.
    """
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

    # Build the message to evaluate
    message = generation.generated_text
    if generation.generated_subject:
        message = f"Subject: {generation.generated_subject}\n\n{message}"

    # Build scenario context
    scenario = db.query(Scenario).filter(Scenario.id == generation.scenario_id).first()
    scenario_context = prompt_service.build_scenario_context_summary(scenario)

    try:
        eval_result = llm_service.evaluate(
            generated_message=message,
            scenario_context=scenario_context,
            model_variant=generation.model_used,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Re-evaluation failed: {str(e)}",
        )

    # Update generation with new scores
    generation.overall_score = eval_result.get("overall_score")
    generation.dimensional_scores = eval_result.get("dimensional_scores")
    generation.evaluation_analysis = eval_result.get("analysis")

    db.commit()
    db.refresh(generation)

    log_action(
        db,
        current_user.id,
        "generation.re_evaluate",
        "generation",
        generation.id,
        details={"new_score": float(generation.overall_score) if generation.overall_score else None},
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return generation


@router.get("/models", response_model=list[dict])
def list_supported_models(
    current_user: User = Depends(get_current_user),
):
    """List supported LLM model variants."""
    models = []
    for key, value in SUPPORTED_MODELS.items():
        models.append({
            "id": key,
            "name": value,
            "description": f"Google Gemini model: {value}",
        })
    return models


@router.get("", response_model=GenerationListResponse)
def list_generations(
    scenario_id: UUID | None = None,
    min_score: float | None = Query(None, ge=0, le=10),
    max_score: float | None = Query(None, ge=0, le=10),
    model: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List generations for the current user with optional filtering."""
    query = (
        db.query(Generation)
        .join(Scenario)
        .filter(Scenario.user_id == current_user.id)
    )

    if scenario_id:
        query = query.filter(Generation.scenario_id == scenario_id)

    if min_score is not None:
        query = query.filter(Generation.overall_score >= min_score)

    if max_score is not None:
        query = query.filter(Generation.overall_score <= max_score)

    if model:
        query = query.filter(Generation.model_used == model)

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


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_generation(
    generation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a generation."""
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

    log_action(
        db,
        current_user.id,
        "generation.delete",
        "generation",
        generation.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    db.delete(generation)
    db.commit()
