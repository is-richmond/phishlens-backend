"""
Pydantic Schemas for Bulk Generation

Request and response models for bulk generation API endpoints.
"""

from typing import Optional, Dict, List, Any
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class BulkGenerationUploadResponse(BaseModel):
    """Response after uploading an Excel file for bulk generation."""

    bulk_generation_id: UUID
    total_rows: int
    column_headers: List[str]
    auto_mapping: Dict[str, str]  # {column_index: placeholder}
    preview_rows: List[Dict[str, Any]]  # First 3 rows


class FieldMappingRequest(BaseModel):
    """Request to update field mapping before generation."""

    field_mapping: Dict[str, str]  # {column_index: placeholder}


class BulkGenerationStartRequest(BaseModel):
    """Request to start bulk generation."""

    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=1024, ge=100, le=4000)
    model_variant: Optional[str] = Field(default="gemini-2.5-flash-lite")


class BulkGenerationProgressResponse(BaseModel):
    """Response showing current progress of bulk generation."""

    bulk_generation_id: UUID
    status: str  # "uploaded", "mapped", "processing", "completed", "failed"
    total_rows: int
    generated_count: int
    failed_count: int
    progress_percent: float


class BulkGenerationResultItem(BaseModel):
    """Individual result from bulk generation."""

    id: UUID
    row_index: int
    input_data: Dict[str, Any]
    generated_subject: Optional[str]
    generated_message: Optional[str]
    status: str  # "pending", "generated", "failed"
    error_message: Optional[str]
    created_at: datetime


class BulkGenerationResultsResponse(BaseModel):
    """Paginated results for bulk generation."""

    results: List[BulkGenerationResultItem]
    pagination: Dict[str, int]  # {"page": 1, "per_page": 20, "total": 95}


class BulkGenerationListItem(BaseModel):
    """Item in list of bulk generations."""

    id: UUID
    title: str
    original_filename: str
    status: str
    total_rows: int
    generated_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime


class BulkGenerationDetailResponse(BaseModel):
    """Detailed view of a bulk generation campaign."""

    id: UUID
    title: str
    original_filename: str
    description: Optional[str]
    status: str
    scenario_id: UUID
    template_id: Optional[UUID]
    field_mapping: Dict[str, str]
    column_headers: List[str] = []  # Excel column headers
    preview_rows: List[Dict[str, Any]] = []  # First 3 sample rows
    total_rows: int
    generated_count: int
    failed_count: int
    temperature: str
    max_tokens: int
    model_variant: str
    created_at: datetime
    updated_at: datetime


class BulkGenerationCreateRequest(BaseModel):
    """Request to create bulk generation campaign with uploaded file."""

    title: str
    scenario_id: UUID
    template_id: Optional[UUID] = None
    description: Optional[str] = None
