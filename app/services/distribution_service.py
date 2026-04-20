"""
Distribution Service

Handles sending distributions (emails) to recipients and tracking delivery status.
Supports multiple email providers: SMTP and SendGrid.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.distribution import Distribution, DistributionStatus
from app.models.bulk_generation import BulkGeneration, BulkGenerationResult
from app.models.campaign import Campaign
from app.models.scenario import Scenario
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("distribution_service")


class DistributionService:
    """Service for managing and sending distributions."""

    @staticmethod
    async def send_via_smtp(
        recipient_email: str,
        subject: str,
        body: str,
        html: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """
        Send email via SMTP server.
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body (HTML or plain text)
            html: Whether body is HTML formatted
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            if not settings.smtp_user or not settings.smtp_password or not settings.email_from:
                raise ValueError("SMTP configuration not complete (user, password, or from address missing)")
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.email_from
            msg["To"] = recipient_email
            
            # Add body
            if html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))
            
            # Send via SMTP
            # For smtp2go port 2525: plain SMTP (no TLS)
            # For smtp2go port 587: SMTP with STARTTLS
            with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
                if settings.smtp_port == 587:
                    server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True, None
            
        except Exception as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def send_via_sendgrid(
        recipient_email: str,
        subject: str,
        body: str,
        html: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """
        Send email via SendGrid API.
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body (HTML or plain text)
            html: Whether body is HTML formatted
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            if not settings.sendgrid_api_key or not settings.sendgrid_from:
                raise ValueError("SendGrid configuration not complete (API key or from address missing)")
            
            message = Mail(
                from_email=settings.sendgrid_from,
                to_emails=recipient_email,
                subject=subject,
                plain_text_content=body if not html else None,
                html_content=body if html else None,
            )
            
            sg = SendGridAPIClient(settings.sendgrid_api_key)
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {recipient_email} via SendGrid")
                return True, None
            else:
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"SendGrid error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def send_distribution(
        db: Session,
        distribution: Distribution,
    ) -> bool:
        """
        Send a single distribution email.
        
        Updates the distribution status based on result.
        """
        try:
            # Choose email provider
            if settings.sendgrid_api_key and settings.sendgrid_from:
                success, error = await DistributionService.send_via_sendgrid(
                    recipient_email=distribution.recipient_email,
                    subject=distribution.subject,
                    body=distribution.body,
                    html=True,
                )
            elif settings.smtp_user and settings.smtp_password and settings.email_from:
                success, error = await DistributionService.send_via_smtp(
                    recipient_email=distribution.recipient_email,
                    subject=distribution.subject,
                    body=distribution.body,
                    html=True,
                )
            else:
                error = "No email provider configured (SMTP or SendGrid)"
                success = False
            
            # Update distribution status
            if success:
                distribution.status = DistributionStatus.SENT
                distribution.sent_at = datetime.utcnow()
            else:
                distribution.status = DistributionStatus.FAILED
                distribution.error_message = error
                distribution.failed_at = datetime.utcnow()
                retry_count = int(distribution.retry_count) + 1
                distribution.retry_count = str(retry_count)
            
            db.commit()
            return success
            
        except Exception as e:
            logger.error(f"Error sending distribution {distribution.id}: {e}")
            distribution.status = DistributionStatus.FAILED
            distribution.error_message = str(e)
            distribution.failed_at = datetime.utcnow()
            db.commit()
            return False

    @staticmethod
    async def send_pending_distributions(
        db: Session,
        batch_size: int = 10,
        delay_between: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Send all pending distributions in batches.
        
        Args:
            db: Database session
            batch_size: Number of emails to send in one batch
            delay_between: Delay in seconds between sends (for rate limiting)
            
        Returns:
            Dictionary with statistics about the send operation
        """
        try:
            # Get pending distributions
            pending = db.query(Distribution).filter(
                Distribution.status == DistributionStatus.PENDING
            ).limit(batch_size).all()
            
            if not pending:
                logger.info("No pending distributions to send")
                return {
                    "sent": 0,
                    "failed": 0,
                    "pending": 0,
                    "total_processed": 0,
                }
            
            results = {
                "sent": 0,
                "failed": 0,
                "total_processed": len(pending),
                "errors": [],
            }
            
            # Send each distribution
            for idx, dist in enumerate(pending):
                success = await DistributionService.send_distribution(db, dist)
                
                if success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "email": dist.recipient_email,
                        "error": dist.error_message,
                    })
                
                # Rate limiting: add delay between sends
                if idx < len(pending) - 1:
                    await asyncio.sleep(delay_between)
            
            # Get remaining pending count
            remaining = db.query(Distribution).filter(
                Distribution.status == DistributionStatus.PENDING
            ).count()
            results["pending"] = remaining
            
            logger.info(
                f"Distribution batch completed: {results['sent']} sent, "
                f"{results['failed']} failed, {remaining} remaining"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch distribution send: {e}")
            return {
                "sent": 0,
                "failed": 0,
                "pending": 0,
                "error": str(e),
            }

    @staticmethod
    def create_distributions_from_bulk_generation(
        db: Session,
        bulk_generation_id: UUID,
        campaign_id: Optional[UUID] = None,
    ) -> tuple[int, Optional[str]]:
        """
        Create Distribution records from bulk generation results.
        
        Called after bulk generation completes. Creates one Distribution
        per generated message.
        
        Args:
            db: Database session
            bulk_generation_id: ID of the bulk generation
            campaign_id: Optional ID of existing campaign
            
        Returns:
            Tuple of (distributions_created: int, error: Optional[str])
        """
        try:
            # Get bulk generation
            bulk_gen = db.query(BulkGeneration).filter(
                BulkGeneration.id == bulk_generation_id
            ).first()
            
            if not bulk_gen:
                return 0, "Bulk generation not found"
            
            # Get all generated results (exclude failed)
            results = db.query(BulkGenerationResult).filter(
                and_(
                    BulkGenerationResult.bulk_generation_id == bulk_generation_id,
                    BulkGenerationResult.status == "generated",
                )
            ).all()
            
            if not results:
                logger.warning(f"No generated results found for bulk generation {bulk_generation_id}")
                return 0, "No generated results found"
            
            # Create distributions
            distributions_created = 0
            for result in results:
                try:
                    # Extract recipient info from field_replacements
                    email = result.field_replacements.get("[TARGET_EMAIL]")
                    name = result.field_replacements.get("[TARGET_NAME]")
                    
                    if not email:
                        logger.warning(f"Row {result.row_index}: No email found in field_replacements")
                        continue
                    
                    # Validate generated content
                    if not result.generated_message:
                        logger.warning(f"Row {result.row_index} ({email}): No message body generated, skipping")
                        continue
                    
                    # Use generated subject, or fallback to a default
                    subject = result.generated_subject
                    if not subject:
                        # Fallback: generate a default subject based on scenario
                        scenario = db.query(Scenario).filter(
                            Scenario.id == bulk_gen.scenario_id
                        ).first()
                        subject = scenario.title or "Security Notification" if scenario else "Security Notification"
                        logger.info(f"Row {result.row_index}: Using fallback subject '{subject}'")
                    
                    # Create distribution
                    distribution = Distribution(
                        bulk_generation_id=bulk_generation_id,
                        campaign_id=campaign_id,
                        recipient_email=email,
                        recipient_name=name,
                        subject=subject,
                        body=result.generated_message,
                        status=DistributionStatus.PENDING,
                    )
                    db.add(distribution)
                    distributions_created += 1
                    logger.debug(f"Created distribution for {email}: subject='{subject[:50]}...'")
                    
                except Exception as e:
                    logger.error(f"Error creating distribution for row {result.row_index}: {e}")
                    continue
            
            db.commit()
            logger.info(f"Created {distributions_created} distributions")
            return distributions_created, None
            
        except Exception as e:
            error_msg = f"Error creating distributions: {str(e)}"
            logger.error(error_msg)
            return 0, error_msg

    @staticmethod
    def get_distribution_stats(
        db: Session,
        campaign_id: Optional[UUID] = None,
    ) -> Dict[str, int]:
        """
        Get statistics about distributions.
        
        Args:
            db: Database session
            campaign_id: Optional filter by campaign
            
        Returns:
            Dictionary with distribution status counts
        """
        query = db.query(Distribution)
        if campaign_id:
            query = query.filter(Distribution.campaign_id == campaign_id)
        
        total = query.count()
        pending = query.filter(Distribution.status == DistributionStatus.PENDING).count()
        sent = query.filter(Distribution.status == DistributionStatus.SENT).count()
        opened = query.filter(Distribution.status == DistributionStatus.OPENED).count()
        clicked = query.filter(Distribution.status == DistributionStatus.CLICKED).count()
        failed = query.filter(Distribution.status == DistributionStatus.FAILED).count()
        
        return {
            "total": total,
            "pending": pending,
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "failed": failed,
            "success_rate": round(sent / total * 100, 2) if total > 0 else 0,
        }


# Singleton instance
distribution_service = DistributionService()
