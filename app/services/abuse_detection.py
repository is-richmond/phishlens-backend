"""
Abuse Detection Service

Detects anomalous usage patterns by comparing per-user generation counts
against the platform mean.  Users exceeding ``mean + N × std_dev``
(default N = 2) are flagged for admin review.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.models.scenario import Scenario
from app.models.user import User
from app.services.audit import log_action
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("abuse_detection")


def _generation_counts_per_user(
    db: Session,
    window_days: int = 30,
) -> list[tuple[UUID, int]]:
    """Return ``(user_id, generation_count)`` for the last *window_days*."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(Scenario.user_id, func.count(Generation.id))
        .join(Generation, Generation.scenario_id == Scenario.id)
        .filter(Generation.created_at >= cutoff)
        .group_by(Scenario.user_id)
        .all()
    )
    return rows  # list of (user_id, count)


def compute_usage_statistics(
    db: Session,
    window_days: int = 30,
) -> dict:
    """Compute mean and standard deviation of generation counts.

    Returns:
        Dict with ``mean``, ``std_dev``, ``threshold``, ``window_days``,
        and ``total_users``.
    """
    counts = _generation_counts_per_user(db, window_days)
    if not counts:
        return {
            "mean": 0.0,
            "std_dev": 0.0,
            "threshold": 0.0,
            "window_days": window_days,
            "total_users": 0,
        }

    values = [c for _, c in counts]
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0.0
    std_dev = math.sqrt(variance)
    threshold = mean + settings.abuse_detection_std_devs * std_dev

    return {
        "mean": round(mean, 2),
        "std_dev": round(std_dev, 2),
        "threshold": round(threshold, 2),
        "window_days": window_days,
        "total_users": n,
    }


def detect_anomalous_users(
    db: Session,
    window_days: int = 30,
) -> list[dict]:
    """Identify users whose generation count exceeds the anomaly threshold.

    The threshold is ``mean + ABUSE_DETECTION_STD_DEVS × std_dev``.

    Returns:
        List of dicts with ``user_id``, ``email``, ``generation_count``,
        ``threshold``, and ``deviation_factor``.
    """
    counts = _generation_counts_per_user(db, window_days)
    if not counts:
        return []

    values = [c for _, c in counts]
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0.0
    std_dev = math.sqrt(variance)
    threshold = mean + settings.abuse_detection_std_devs * std_dev

    flagged: list[dict] = []
    for user_id, count in counts:
        if count > threshold and std_dev > 0:
            deviation_factor = round((count - mean) / std_dev, 2)
            user = db.query(User).filter(User.id == user_id).first()
            flagged.append({
                "user_id": str(user_id),
                "email": user.email if user else "unknown",
                "full_name": user.full_name if user else "unknown",
                "generation_count": count,
                "threshold": round(threshold, 2),
                "deviation_factor": deviation_factor,
            })

    # Sort by deviation factor descending
    flagged.sort(key=lambda x: x["deviation_factor"], reverse=True)

    return flagged


def check_user_abuse(
    db: Session,
    user_id: UUID,
    window_days: int = 30,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Check whether *user_id* is currently above the anomaly threshold.

    If flagged, an audit log entry is created automatically.

    Returns:
        ``True`` if the user is flagged as anomalous, ``False`` otherwise.
    """
    stats = compute_usage_statistics(db, window_days)
    threshold = stats["threshold"]
    if threshold == 0:
        return False

    # Count this user's generations in the window
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    user_count = (
        db.query(func.count(Generation.id))
        .join(Scenario, Scenario.id == Generation.scenario_id)
        .filter(Scenario.user_id == user_id, Generation.created_at >= cutoff)
        .scalar()
    ) or 0

    if user_count > threshold and stats["std_dev"] > 0:
        deviation = round((user_count - stats["mean"]) / stats["std_dev"], 2)
        logger.warning(
            "Abuse detection: user exceeds threshold",
            user_id=str(user_id),
            generation_count=user_count,
            threshold=threshold,
            deviation_factor=deviation,
        )
        log_action(
            db,
            user_id,
            "ethics.abuse_alert",
            "user",
            user_id,
            details={
                "generation_count": user_count,
                "threshold": threshold,
                "mean": stats["mean"],
                "std_dev": stats["std_dev"],
                "deviation_factor": deviation,
                "window_days": window_days,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return True

    return False
