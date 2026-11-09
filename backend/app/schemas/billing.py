from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.workspace import WorkspacePlan


class PlanLimits(BaseModel):
    max_memories: int
    max_documents: int
    max_storage_bytes: int
    max_ai_queries: int


class PlanInfo(BaseModel):
    tier: WorkspacePlan
    name: str
    price_monthly: int
    currency: str = "USD"
    description: str
    limits: PlanLimits
    features: list[str]


PLAN_CATALOG: dict[WorkspacePlan, PlanInfo] = {
    WorkspacePlan.FREE: PlanInfo(
        tier=WorkspacePlan.FREE,
        name="Free Tier",
        price_monthly=0,
        currency="USD",
        description="For personal exploration and note taking",
        limits=PlanLimits(
            max_memories=100,
            max_documents=5,
            max_storage_bytes=50 * 1024 * 1024,  # 50 MB
            max_ai_queries=100,
        ),
        features=[
            "100 Verified Memories",
            "5 Ingested Documents",
            "50 MB Secure Storage",
            "Lexical & Semantic Search",
            "Standard Review Inbox",
        ],
    ),
    WorkspacePlan.PERSONAL: PlanInfo(
        tier=WorkspacePlan.PERSONAL,
        name="Personal Pro",
        price_monthly=15,
        currency="USD",
        description="For researchers, writers, and knowledge workers",
        limits=PlanLimits(
            max_memories=2500,
            max_documents=50,
            max_storage_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
            max_ai_queries=2000,
        ),
        features=[
            "2,500 Long-Term Memories",
            "50 Multi-Format Documents",
            "2 GB Cloud Object Storage",
            "2,000 AI RAG Queries / mo",
            "Voice Speech-to-Text & TTS",
            "Temporal Validity & Timeline",
            "Conflict & Contradiction Alerts",
        ],
    ),
    WorkspacePlan.PRO: PlanInfo(
        tier=WorkspacePlan.PRO,
        name="Executive Knowledge",
        price_monthly=39,
        currency="USD",
        description="Power knowledge intelligence with full autonomy",
        limits=PlanLimits(
            max_memories=25000,
            max_documents=500,
            max_storage_bytes=25 * 1024 * 1024 * 1024,  # 25 GB
            max_ai_queries=20000,
        ),
        features=[
            "25,000 Memory Vault Records",
            "500 Ingested Documents",
            "25 GB Cloud Storage",
            "Interactive Knowledge Graph",
            "Multi-Document Research Lab",
            "Autonomous Agents & Tool Registry",
            "Developer API Keys & Webhooks",
            "Proactive Smart Insights",
        ],
    ),
    WorkspacePlan.TEAM: PlanInfo(
        tier=WorkspacePlan.TEAM,
        name="Team Enterprise",
        price_monthly=99,
        currency="USD",
        description="Organization-wide intelligence and shared graph context",
        limits=PlanLimits(
            max_memories=1000000,
            max_documents=5000,
            max_storage_bytes=250 * 1024 * 1024 * 1024,  # 250 GB
            max_ai_queries=100000,
        ),
        features=[
            "Unlimited Long-Term Memories",
            "5,000 Ingested Documents",
            "250 GB High-Throughput Storage",
            "Multi-Tenant Shared Workspaces",
            "Audit Log Trail & Compliance",
            "Dedicated Background Workers",
            "SSRF-Protected URL Crawling",
            "Priority Support & SLA",
        ],
    ),
}


class UsageMetric(BaseModel):
    used: int
    limit: int
    percentage: float
    unit: str


class WorkspaceUsageResponse(BaseModel):
    plan_tier: WorkspacePlan
    memories: UsageMetric
    documents: UsageMetric
    storage: UsageMetric
    ai_queries: UsageMetric


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    amount_cents: int
    currency: str
    status: str
    invoice_url: str | None = None
    paid_at: datetime | None = None
    created_at: datetime


class SubscriptionResponse(BaseModel):
    id: str
    workspace_id: str
    plan_tier: WorkspacePlan
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    invoices: list[InvoiceResponse] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    plan_tier: WorkspacePlan
    success_url: str | None = None
    cancel_url: str | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    plan_tier: WorkspacePlan


class AuditEventResponse(BaseModel):
    id: str
    workspace_id: str | None = None
    user_id: str | None = None
    action: str
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditChainVerificationResponse(BaseModel):
    is_valid: bool
    total_records_checked: int
    tampered_record_id: str | None = None
    chain_head_hash: str
    message: str
    verified_at: datetime


class SystemOverviewResponse(BaseModel):
    total_users: int
    total_workspaces: int
    total_memories: int
    total_documents: int
    plans_distribution: dict[str, int]
    health: dict[str, Any]


class MerkleAuditRootRequest(BaseModel):
    workspace_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    action_filter: str | None = None


class MerkleAuditRootResponse(BaseModel):
    merkle_root: str
    total_leaves: int
    tree_depth: int
    workspace_id: str | None = None
    generated_at: datetime


class MerkleProofRequest(BaseModel):
    event_id: str
    workspace_id: str | None = None


class MerkleProofResponse(BaseModel):
    event_id: str
    action: str
    leaf_hash: str
    leaf_index: int
    merkle_root: str
    total_leaves: int
    audit_path: list[dict[str, str]]
    generated_at: datetime


class MerkleProofVerificationRequest(BaseModel):
    leaf_hash: str
    merkle_root: str
    audit_path: list[dict[str, str]]


class MerkleProofVerificationResponse(BaseModel):
    is_valid: bool
    computed_root: str
    expected_root: str
    message: str
    verified_at: datetime
