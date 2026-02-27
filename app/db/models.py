"""Pydantic models and enums for TenderAI entities."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class RFPStatus(str, Enum):
    NEW = "new"
    ANALYZING = "analyzing"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AWARDED = "awarded"
    LOST = "lost"
    CANCELLED = "cancelled"


class ProposalType(str, Enum):
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    COMBINED = "combined"


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    FINAL = "final"
    SUBMITTED = "submitted"


class NDAStatus(str, Enum):
    NONE = "none"
    SENT = "sent"
    SIGNED = "signed"
    EXPIRED = "expired"


class DeliverableType(str, Enum):
    TECHNICAL_INPUT = "technical_input"
    PRICING = "pricing"
    CV = "cv"
    REFERENCE_LETTER = "reference_letter"
    CERTIFICATION = "certification"
    DOCUMENT = "document"
    OTHER = "other"


class DeliverableStatus(str, Enum):
    PENDING = "pending"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    RECEIVED = "received"
    APPROVED = "approved"
    OVERDUE = "overdue"


# --- Models ---

class RFP(BaseModel):
    id: str
    title: str
    client: str
    sector: str = "telecom"
    country: str = "OM"
    rfp_number: Optional[str] = None
    issue_date: Optional[str] = None
    deadline: Optional[str] = None
    submission_method: Optional[str] = None
    status: RFPStatus = RFPStatus.NEW
    file_path: Optional[str] = None
    parsed_sections: dict = Field(default_factory=dict)
    requirements: list = Field(default_factory=list)
    evaluation_criteria: list = Field(default_factory=list)
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProposalSection(BaseModel):
    section_id: str
    title: str
    content: str
    order: int


class Proposal(BaseModel):
    id: str
    rfp_id: str
    proposal_type: ProposalType
    status: ProposalStatus = ProposalStatus.DRAFT
    title: str = ""
    sections: list[ProposalSection] = Field(default_factory=list)
    output_path: Optional[str] = None
    version: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Vendor(BaseModel):
    id: str
    name: str
    category: str = "general"
    specialization: str = ""
    country: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    currency: str = "USD"
    past_projects: list = Field(default_factory=list)
    notes: str = ""
    is_approved: bool = False
    rating: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BOMItem(BaseModel):
    id: str
    proposal_id: str
    category: str
    item_name: str
    description: str = ""
    vendor_id: Optional[str] = None
    manufacturer: str = ""
    part_number: str = ""
    quantity: float = 1.0
    unit: str = "unit"
    unit_cost: float = 0.0
    margin_pct: float = 15.0
    total_cost: Optional[float] = None
    warranty_months: int = 12
    sort_order: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Partner(BaseModel):
    id: str
    name: str
    country: str = ""
    specialization: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    nda_status: NDAStatus = NDAStatus.NONE
    nda_signed_date: Optional[str] = None
    nda_expiry_date: Optional[str] = None
    past_projects: list = Field(default_factory=list)
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PartnerDeliverable(BaseModel):
    id: str
    partner_id: str
    proposal_id: str
    title: str
    deliverable_type: DeliverableType = DeliverableType.DOCUMENT
    due_date: Optional[str] = None
    status: DeliverableStatus = DeliverableStatus.PENDING
    file_path: Optional[str] = None
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
