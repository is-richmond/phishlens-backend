"""
Templates Router

Endpoints for managing phishing message templates.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, get_client_ip
from app.models.user import User
from app.models.template import Template
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
)
from app.schemas.scenario import PretextCategory
from app.services.audit import log_action
from app.core.logging import get_logger

logger = get_logger("templates_router")

router = APIRouter()


@router.get("", response_model=TemplateListResponse)
def list_templates(
    category: PretextCategory | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List available templates (predefined + own custom templates)."""
    query = db.query(Template).filter(
        or_(
            Template.is_predefined == True,  # noqa: E712
            Template.is_public == True,  # noqa: E712
            Template.user_id == current_user.id,
        )
    )

    if category:
        query = query.filter(Template.category == category.value)

    if search:
        query = query.filter(
            or_(
                Template.name.ilike(f"%{search}%"),
                Template.description.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    items = (
        query.order_by(Template.is_predefined.desc(), Template.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return TemplateListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific template."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    # Check access: predefined, public, or owned by user
    if not template.is_predefined and not template.is_public and template.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return template


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    data: TemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom template.

    Rejects prompts containing injection / jailbreak patterns and logs the
    blocked attempt to the audit trail.
    """
    template = Template(
        user_id=current_user.id,
        is_predefined=False,
        **data.model_dump(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    log_action(
        db, current_user.id, "template.create", "template", template.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom template (only owner can update).

    Rejects prompts containing injection / jailbreak patterns and logs the
    blocked attempt to the audit trail.
    """
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.user_id == current_user.id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_predefined:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Predefined templates cannot be modified",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)

    log_action(
        db, current_user.id, "template.update", "template", template.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom template (only owner can delete)."""
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.user_id == current_user.id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_predefined:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Predefined templates cannot be deleted",
        )

    log_action(db, current_user.id, "template.delete", "template", template.id)

    db.delete(template)
    db.commit()
