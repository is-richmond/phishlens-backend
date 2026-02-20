"""
Campaigns Router

Endpoints for organizing generations into research campaigns
with aggregate statistics and analysis.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_db, get_current_user, get_client_ip
from app.models.user import User
from app.models.campaign import Campaign, campaign_generations
from app.models.generation import Generation
from app.models.scenario import Scenario
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignDetailResponse,
    CampaignAddGeneration,
    CampaignListResponse,
)

from app.services.audit import log_action

router = APIRouter()


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    data: CampaignCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new campaign."""
    campaign = Campaign(user_id=current_user.id, **data.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    log_action(
        db,
        current_user.id,
        "campaign.create",
        "campaign",
        campaign.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return campaign


@router.get("/", response_model=CampaignListResponse)
def list_campaigns(
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List campaigns owned by the current user."""
    query = db.query(Campaign).filter(Campaign.user_id == current_user.id)

    if search:
        from sqlalchemy import or_
        term = f"%{search}%"
        query = query.filter(
            or_(
                Campaign.name.ilike(term),
                Campaign.description.ilike(term),
            )
        )

    total = query.count()
    items = (
        query.order_by(Campaign.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return CampaignListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a campaign with its associated generations."""
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Calculate aggregate stats
    scores = [g.overall_score for g in campaign.generations if g.overall_score is not None]
    avg_score = sum(scores) / len(scores) if scores else None

    return CampaignDetailResponse(
        id=campaign.id,
        user_id=campaign.user_id,
        name=campaign.name,
        description=campaign.description,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        generations=campaign.generations,
        total_generations=len(campaign.generations),
        average_score=float(avg_score) if avg_score else None,
    )


@router.get("/{campaign_id}/statistics")
def get_campaign_statistics(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed statistics for a campaign.

    Includes score breakdown, model distribution, category coverage,
    and per-dimension score analysis.
    """
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    generations = campaign.generations
    total = len(generations)
    scores = [float(g.overall_score) for g in generations if g.overall_score is not None]

    # Model distribution
    model_counts: dict[str, int] = {}
    for g in generations:
        model_counts[g.model_used] = model_counts.get(g.model_used, 0) + 1

    # Dimensional score averages
    dim_scores: dict[str, list[float]] = {
        "linguistic_naturalness": [],
        "psychological_triggers": [],
        "technical_plausibility": [],
        "contextual_relevance": [],
    }
    for g in generations:
        if g.dimensional_scores:
            for dim in dim_scores:
                val = g.dimensional_scores.get(dim)
                if val is not None:
                    dim_scores[dim].append(float(val))

    dim_averages = {
        dim: round(sum(vals) / len(vals), 2) if vals else None
        for dim, vals in dim_scores.items()
    }

    # Category distribution (via scenario)
    category_counts: dict[str, int] = {}
    for g in generations:
        scenario = db.query(Scenario).filter(Scenario.id == g.scenario_id).first()
        if scenario:
            cat = scenario.pretext_category
            category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "campaign_id": str(campaign.id),
        "campaign_name": campaign.name,
        "total_generations": total,
        "scored_generations": len(scores),
        "scores": {
            "average": round(sum(scores) / len(scores), 2) if scores else None,
            "min": round(min(scores), 2) if scores else None,
            "max": round(max(scores), 2) if scores else None,
            "median": round(sorted(scores)[len(scores) // 2], 2) if scores else None,
        },
        "dimensional_averages": dim_averages,
        "model_distribution": model_counts,
        "category_distribution": category_counts,
    }


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a campaign."""
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)

    log_action(db, current_user.id, "campaign.update", "campaign", campaign.id)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a campaign (does not delete associated generations)."""
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    log_action(db, current_user.id, "campaign.delete", "campaign", campaign.id)

    db.delete(campaign)
    db.commit()


@router.post("/{campaign_id}/generations", status_code=status.HTTP_201_CREATED)
def add_generation_to_campaign(
    campaign_id: UUID,
    data: CampaignAddGeneration,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a generation to a campaign."""
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Verify generation ownership
    generation = (
        db.query(Generation)
        .join(Scenario)
        .filter(Generation.id == data.generation_id, Scenario.user_id == current_user.id)
        .first()
    )
    if not generation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")

    # Check if already associated
    if generation in campaign.generations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generation is already in this campaign",
        )

    campaign.generations.append(generation)
    db.commit()

    log_action(
        db,
        current_user.id,
        "campaign.add_generation",
        "campaign",
        campaign.id,
        details={"generation_id": str(data.generation_id)},
    )
    return {"message": "Generation added to campaign"}


@router.delete("/{campaign_id}/generations/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_generation_from_campaign(
    campaign_id: UUID,
    generation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a generation from a campaign."""
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    generation = db.query(Generation).filter(Generation.id == generation_id).first()
    if not generation or generation not in campaign.generations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found in this campaign",
        )

    campaign.generations.remove(generation)
    db.commit()
