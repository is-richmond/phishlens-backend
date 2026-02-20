"""
Export Router

Endpoints for exporting generations in multiple formats (JSON, CSV, EML).
"""

import csv
import io
import json
from email.mime.text import MIMEText
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.generation import Generation
from app.models.scenario import Scenario

router = APIRouter()


@router.post("/")
def export_generations(
    generation_ids: list[UUID],
    format: str = Query("json", regex="^(json|csv|eml)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export selected generations in the specified format.

    Supported formats: json, csv, eml
    """
    # Fetch generations with ownership check
    generations = (
        db.query(Generation)
        .join(Scenario)
        .filter(
            Generation.id.in_(generation_ids),
            Scenario.user_id == current_user.id,
        )
        .all()
    )

    if not generations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No generations found",
        )

    if format == "json":
        return _export_json(generations)
    elif format == "csv":
        return _export_csv(generations)
    elif format == "eml":
        return _export_eml(generations)


def _export_json(generations: list[Generation]) -> StreamingResponse:
    """Export generations as JSON."""
    data = []
    for gen in generations:
        data.append({
            "id": str(gen.id),
            "scenario_id": str(gen.scenario_id),
            "template_id": str(gen.template_id) if gen.template_id else None,
            "subject": gen.generated_subject,
            "body": gen.generated_text,
            "model": gen.model_used,
            "overall_score": float(gen.overall_score) if gen.overall_score else None,
            "dimensional_scores": gen.dimensional_scores,
            "evaluation_analysis": gen.evaluation_analysis,
            "parameters": gen.input_parameters,
            "watermark": gen.watermark,
            "created_at": gen.created_at.isoformat(),
        })

    content = json.dumps(data, indent=2, ensure_ascii=False)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=phishlens_export.json"},
    )


def _export_csv(generations: list[Generation]) -> StreamingResponse:
    """Export generations as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Scenario ID", "Subject", "Body", "Model",
        "Overall Score", "Linguistic Naturalness", "Psychological Triggers",
        "Technical Plausibility", "Contextual Relevance",
        "Watermark", "Created At",
    ])

    for gen in generations:
        scores = gen.dimensional_scores or {}
        writer.writerow([
            str(gen.id),
            str(gen.scenario_id),
            gen.generated_subject or "",
            gen.generated_text,
            gen.model_used,
            float(gen.overall_score) if gen.overall_score else "",
            scores.get("linguistic_naturalness", ""),
            scores.get("psychological_triggers", ""),
            scores.get("technical_plausibility", ""),
            scores.get("contextual_relevance", ""),
            gen.watermark,
            gen.created_at.isoformat(),
        ])

    content = output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=phishlens_export.csv"},
    )


def _export_eml(generations: list[Generation]) -> StreamingResponse:
    """Export generations as EML (RFC 5322 email format)."""
    eml_parts = []
    for gen in generations:
        msg = MIMEText(
            f"{gen.generated_text}\n\n---\n{gen.watermark}\nGeneration ID: {gen.id}",
            "plain",
            "utf-8",
        )
        msg["Subject"] = gen.generated_subject or "[No Subject]"
        msg["From"] = "[SENDER_PLACEHOLDER]@example-phishing-domain.test"
        msg["To"] = "[TARGET_PLACEHOLDER]@[COMPANY_EMAIL]"
        msg["Date"] = gen.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg["X-PhishLens-ID"] = str(gen.id)
        msg["X-PhishLens-Watermark"] = gen.watermark
        eml_parts.append(msg.as_string())

    content = "\n\n".join(eml_parts)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="message/rfc822",
        headers={"Content-Disposition": "attachment; filename=phishlens_export.eml"},
    )
