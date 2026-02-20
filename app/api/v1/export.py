"""
Export Router

Endpoints for exporting generations in multiple formats (JSON, CSV, EML)
with rich metadata including scenario details and campaign context.
"""

import csv
import io
import json
from datetime import datetime, timezone
from email.mime.text import MIMEText
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, get_client_ip
from app.models.user import User
from app.models.generation import Generation
from app.models.scenario import Scenario
from app.services.audit import log_action

router = APIRouter()


@router.post("/")
def export_generations(
    generation_ids: list[UUID],
    request: Request,
    format: str = Query("json", regex="^(json|csv|eml)$"),
    include_metadata: bool = Query(True, description="Include scenario/template metadata in export"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export selected generations in the specified format.

    Supported formats: json, csv, eml.
    Optionally includes scenario and template metadata.
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

    # Preload scenarios for metadata
    scenario_map = {}
    if include_metadata:
        scenario_ids = {g.scenario_id for g in generations}
        scenarios = db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()
        scenario_map = {s.id: s for s in scenarios}

    log_action(
        db,
        current_user.id,
        "export.create",
        "generation",
        details={
            "format": format,
            "count": len(generations),
            "generation_ids": [str(g.id) for g in generations],
        },
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    if format == "json":
        return _export_json(generations, scenario_map, include_metadata)
    elif format == "csv":
        return _export_csv(generations, scenario_map, include_metadata)
    elif format == "eml":
        return _export_eml(generations, scenario_map)


def _export_json(
    generations: list[Generation],
    scenario_map: dict,
    include_metadata: bool,
) -> StreamingResponse:
    """Export generations as JSON with optional metadata."""
    export_data = {
        "export_info": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "platform": "PhishLens",
            "total_items": len(generations),
            "disclaimer": "This data was generated for authorized cybersecurity research only.",
        },
        "generations": [],
    }

    for gen in generations:
        item = {
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
            "generation_time_ms": gen.generation_time_ms,
            "created_at": gen.created_at.isoformat(),
        }

        if include_metadata and gen.scenario_id in scenario_map:
            scenario = scenario_map[gen.scenario_id]
            item["scenario_metadata"] = {
                "title": scenario.title,
                "target_role": scenario.target_role,
                "target_department": scenario.target_department,
                "pretext_category": scenario.pretext_category,
                "communication_channel": scenario.communication_channel,
                "urgency_level": scenario.urgency_level,
                "language": scenario.language,
            }

        export_data["generations"].append(item)

    content = json.dumps(export_data, indent=2, ensure_ascii=False)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=phishlens_export.json"},
    )


def _export_csv(
    generations: list[Generation],
    scenario_map: dict,
    include_metadata: bool,
) -> StreamingResponse:
    """Export generations as CSV with optional metadata columns."""
    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "ID", "Scenario ID", "Subject", "Body", "Model",
        "Overall Score", "Linguistic Naturalness", "Psychological Triggers",
        "Technical Plausibility", "Contextual Relevance",
        "Generation Time (ms)", "Watermark", "Created At",
    ]
    if include_metadata:
        headers.extend([
            "Scenario Title", "Target Role", "Target Department",
            "Pretext Category", "Channel", "Urgency Level", "Language",
        ])
    writer.writerow(headers)

    for gen in generations:
        scores = gen.dimensional_scores or {}
        row = [
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
            gen.generation_time_ms or "",
            gen.watermark,
            gen.created_at.isoformat(),
        ]

        if include_metadata and gen.scenario_id in scenario_map:
            scenario = scenario_map[gen.scenario_id]
            row.extend([
                scenario.title,
                scenario.target_role,
                scenario.target_department or "",
                scenario.pretext_category,
                scenario.communication_channel,
                scenario.urgency_level,
                scenario.language,
            ])
        elif include_metadata:
            row.extend([""] * 7)

        writer.writerow(row)

    content = output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=phishlens_export.csv"},
    )


def _export_eml(
    generations: list[Generation],
    scenario_map: dict,
) -> StreamingResponse:
    """Export generations as EML (RFC 5322 email format) with metadata headers."""
    eml_parts = []
    for gen in generations:
        body_parts = [gen.generated_text, f"\n\n---\n{gen.watermark}\nGeneration ID: {gen.id}"]

        # Add metadata footer if scenario available
        if gen.scenario_id in scenario_map:
            scenario = scenario_map[gen.scenario_id]
            body_parts.append(
                f"\n--- PhishLens Metadata ---\n"
                f"Scenario: {scenario.title}\n"
                f"Category: {scenario.pretext_category}\n"
                f"Target Role: {scenario.target_role}\n"
                f"Channel: {scenario.communication_channel}\n"
                f"Urgency: {scenario.urgency_level}/5\n"
                f"Score: {gen.overall_score or 'N/A'}\n"
            )

        msg = MIMEText("".join(body_parts), "plain", "utf-8")
        msg["Subject"] = gen.generated_subject or "[No Subject]"
        msg["From"] = "[SENDER_PLACEHOLDER]@example-phishing-domain.test"
        msg["To"] = "[TARGET_PLACEHOLDER]@[COMPANY_EMAIL]"
        msg["Date"] = gen.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg["X-PhishLens-ID"] = str(gen.id)
        msg["X-PhishLens-Watermark"] = gen.watermark
        msg["X-PhishLens-Model"] = gen.model_used
        if gen.overall_score:
            msg["X-PhishLens-Score"] = str(gen.overall_score)
        eml_parts.append(msg.as_string())

    content = "\n\n".join(eml_parts)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="message/rfc822",
        headers={"Content-Disposition": "attachment; filename=phishlens_export.eml"},
    )
