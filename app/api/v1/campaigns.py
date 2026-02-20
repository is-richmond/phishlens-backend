"""
Campaigns Router

Endpoints for organizing generations into research campaigns.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_db, get_current_user
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new campaign."""
    campaign = Campaign(user_id=current_user.id, **data.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    log_action(db, current_user.id, "campaign.create", "campaign", campaign.id)
    return campaign


@router.get("/", response_model=CampaignListResponse)
def list_campaigns(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List campaigns owned by the current user."""
    query = db.query(Campaign).filter(Campaign.user_id == current_user.id)
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
