"""
Bulk Generation Service

Handles the orchestration of bulk generation from Excel files.
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bulk_generation import BulkGeneration, BulkGenerationResult
from app.models.scenario import Scenario
from app.models.template import Template
from app.services.generation_service import generation_service
from app.services.excel_service import excel_service
from app.core.logging import get_logger

logger = get_logger("bulk_generation_service")


class BulkGenerationService:
    """Service for orchestrating bulk generation."""

    def create_bulk_generation(
        self,
        db: Session,
        user_id: UUID,
        title: str,
        original_filename: str,
        file_data: bytes,
        scenario_id: UUID,
        template_id: Optional[UUID],
        description: Optional[str] = None,
    ) -> BulkGeneration:
        """Create a new bulk generation campaign from uploaded file.

        Args:
            db: Database session
            user_id: User who uploaded the file
            title: Campaign title
            original_filename: Original filename
            file_data: Raw Excel file bytes
            scenario_id: Scenario to use for generation
            template_id: Optional template to use
            description: Optional campaign description

        Returns:
            Created BulkGeneration record
        """
        # Parse Excel file
        headers, rows, total_rows = excel_service.parse_excel_file(file_data)
        logger.info(f"Parsed {total_rows} rows from {original_filename}")

        # Auto-detect field mapping
        auto_mapping = excel_service.auto_detect_field_mapping(headers)

        # Create BulkGeneration record
        bulk_gen = BulkGeneration(
            user_id=user_id,
            title=title,
            original_filename=original_filename,
            file_data=file_data,
            scenario_id=scenario_id,
            template_id=template_id,
            description=description,
            field_mapping=auto_mapping,
            total_rows=total_rows,
            status="uploaded",
        )

        db.add(bulk_gen)
        db.flush()  # Get the ID without committing yet

        # Create BulkGenerationResult records for each row
        for row_idx, row_data in enumerate(rows):
            result = BulkGenerationResult(
                bulk_generation_id=bulk_gen.id,
                row_index=row_idx,
                input_data=row_data,
                status="pending",
            )
            db.add(result)

        db.commit()
        logger.info(f"Created BulkGeneration {bulk_gen.id} with {len(rows)} rows")

        return bulk_gen

    def get_mapping_preview(
        self, bulk_gen: BulkGeneration
    ) -> Dict[str, Any]:
        """Get preview for field mapping."""
        # Re-parse to get headers and sample rows
        headers, rows, _ = excel_service.parse_excel_file(bulk_gen.file_data)

        return {
            "column_headers": headers,
            "field_mapping": bulk_gen.field_mapping,
            "preview_rows": rows[:3],  # First 3 rows
        }

    def update_field_mapping(
        self, db: Session, bulk_gen_id: UUID, field_mapping: Dict[str, str]
    ) -> BulkGeneration:
        """Update field mapping for bulk generation.

        Args:
            db: Database session
            bulk_gen_id: BulkGeneration ID
            field_mapping: New field mapping

        Returns:
            Updated BulkGeneration record
        """
        bulk_gen = db.query(BulkGeneration).filter(BulkGeneration.id == bulk_gen_id).first()
        if not bulk_gen:
            raise ValueError(f"BulkGeneration {bulk_gen_id} not found")

        # Validate mapping
        headers, _, _ = excel_service.parse_excel_file(bulk_gen.file_data)
        is_valid, errors = excel_service.validate_mapping(field_mapping, headers)

        if not is_valid:
            raise ValueError(f"Invalid mapping: {', '.join(errors)}")

        bulk_gen.field_mapping = field_mapping
        bulk_gen.status = "mapped"
        db.commit()
        logger.info(f"Updated mapping for BulkGeneration {bulk_gen_id}")

        return bulk_gen

    async def process_bulk_generation_async(
        self,
        db: Session,
        bulk_gen_id: UUID,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_variant: str = "gemini-2.5-flash-lite",
    ) -> BulkGeneration:
        """Process bulk generation asynchronously.

        Generates messages for all rows and stores results.

        Args:
            db: Database session (initial session, will create new one for async context)
            bulk_gen_id: BulkGeneration ID to process
            temperature: LLM temperature
            max_tokens: Max tokens for generation
            model_variant: Model variant to use

        Returns:
            Updated BulkGeneration record with completion status
        """
        # Create a new database session for this async task
        # (the passed db session may be tied to the request context)
        from app.database import SessionLocal
        
        async_db = SessionLocal()
        
        try:
            bulk_gen = async_db.query(BulkGeneration).filter(BulkGeneration.id == bulk_gen_id).first()
            if not bulk_gen:
                raise ValueError(f"BulkGeneration {bulk_gen_id} not found")

            logger.info(f"Starting bulk generation for {bulk_gen_id}")
            bulk_gen.status = "processing"
            async_db.commit()

            # Get scenario and template
            scenario = async_db.query(Scenario).filter(Scenario.id == bulk_gen.scenario_id).first()
            template = None
            if bulk_gen.template_id:
                template = async_db.query(Template).filter(Template.id == bulk_gen.template_id).first()

            # Parse Excel data
            headers, rows, _ = excel_service.parse_excel_file(bulk_gen.file_data)

            # Get all pending results
            results = (
                async_db.query(BulkGenerationResult)
                .filter(BulkGenerationResult.bulk_generation_id == bulk_gen_id)
                .filter(BulkGenerationResult.status == "pending")
                .all()
            )

            logger.info(f"Processing {len(results)} rows for {bulk_gen_id}")

            generated_count = 0
            failed_count = 0

            for idx, result in enumerate(results):
                try:
                    # Apply field replacements
                    replacements = excel_service.apply_field_replacements(
                        result.input_data, headers, bulk_gen.field_mapping
                    )

                    logger.debug(f"Row {result.row_index}: replacements = {replacements}")

                    # Generate message with replacements
                    generation = generation_service.generate(
                        db=async_db,
                        scenario=scenario,
                        template=template,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model_variant=model_variant,
                        field_replacements=replacements,
                        bulk_generation_id=bulk_gen_id,
                    )

                    # Update result
                    result.generation_id = generation.id
                    result.generated_subject = generation.generated_subject
                    result.generated_message = generation.generated_text
                    result.field_replacements = replacements
                    result.status = "generated"
                    result.error_message = None

                    generated_count += 1
                    logger.info(f"[{idx + 1}/{len(results)}] Generated row {result.row_index}")

                except Exception as e:
                    logger.error(f"Error generating row {result.row_index}: {e}", exc_info=True)
                    result.status = "failed"
                    result.error_message = str(e)
                    failed_count += 1

                # Update progress in database
                async_db.commit()

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)

            # Final update: set completed status
            bulk_gen.generated_count = generated_count
            bulk_gen.failed_count = failed_count
            bulk_gen.status = "completed"
            bulk_gen.temperature = str(temperature)
            bulk_gen.max_tokens = max_tokens
            bulk_gen.model_variant = model_variant

            async_db.commit()
            logger.info(
                f"✓ Bulk generation {bulk_gen_id} completed: {generated_count} generated, {failed_count} failed"
            )

            return bulk_gen

        except Exception as e:
            logger.error(f"Fatal error in bulk generation {bulk_gen_id}: {e}", exc_info=True)
            bulk_gen = async_db.query(BulkGeneration).filter(BulkGeneration.id == bulk_gen_id).first()
            if bulk_gen:
                bulk_gen.status = "failed"
                async_db.commit()
            raise
        finally:
            async_db.close()

    def get_bulk_generation_progress(
        self, db: Session, bulk_gen_id: UUID
    ) -> Dict[str, Any]:
        """Get current progress of bulk generation.

        Args:
            db: Database session
            bulk_gen_id: BulkGeneration ID

        Returns:
            Progress dictionary
        """
        bulk_gen = db.query(BulkGeneration).filter(BulkGeneration.id == bulk_gen_id).first()
        if not bulk_gen:
            raise ValueError(f"BulkGeneration {bulk_gen_id} not found")

        progress_percent = 0
        if bulk_gen.total_rows > 0:
            completed = bulk_gen.generated_count + bulk_gen.failed_count
            progress_percent = int((completed / bulk_gen.total_rows) * 100)

        return {
            "status": bulk_gen.status,
            "total_rows": bulk_gen.total_rows,
            "generated_count": bulk_gen.generated_count,
            "failed_count": bulk_gen.failed_count,
            "progress_percent": progress_percent,
        }

    def get_bulk_generation_results(
        self,
        db: Session,
        bulk_gen_id: UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """Get paginated results for bulk generation.

        Args:
            db: Database session
            bulk_gen_id: BulkGeneration ID
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Paginated results dictionary
        """
        # Get total count
        total = (
            db.query(BulkGenerationResult)
            .filter(BulkGenerationResult.bulk_generation_id == bulk_gen_id)
            .count()
        )

        # Get paginated results
        skip = (page - 1) * per_page
        results = (
            db.query(BulkGenerationResult)
            .filter(BulkGenerationResult.bulk_generation_id == bulk_gen_id)
            .order_by(BulkGenerationResult.row_index)
            .offset(skip)
            .limit(per_page)
            .all()
        )

        return {
            "results": results,
            "pagination": {"page": page, "per_page": per_page, "total": total},
        }


bulk_generation_service = BulkGenerationService()
