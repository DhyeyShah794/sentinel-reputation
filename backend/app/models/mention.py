"""
Data models for the Sentinel Reputation Intelligence Platform.

Three-stage model hierarchy:
  RawMention       → Direct parse from XLSX, minimal transformation
  CleanedMention   → After cleaning, standardization, dedup
  ProcessedMention → After classification, sentiment, enrichment (final)
"""


import datetime
import uuid
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SourceType(str, Enum):
    NEWS = "news"
    FORUM = "forum"
    REVIEW = "review"
    PROFESSIONAL = "professional"
    AGGREGATOR = "aggregator"
    UNKNOWN = "unknown"


class ReputationDriver(str, Enum):
    BRAND_PERCEPTION = "Brand Perception"
    USER_EXPERIENCE = "User Experience"
    RESPONSIBLE_BUSINESS = "Responsible Business Practices"


class SubDriver(str, Enum):
    # Brand Perception
    THOUGHT_LEADERSHIP = "Thought Leadership"
    PRODUCT_STRATEGY = "Product Strategy"
    BRAND_VISIBILITY = "Brand Visibility & Marketing"
    # User Experience
    PRODUCT_SERVICE_QUALITY = "Product & Service Quality"
    CUSTOMER_SUPPORT = "Customer Support & Complaint Resolution"
    DIGITAL_EXPERIENCE = "Digital & Omnichannel Experience"
    # Responsible Business Practices
    REGULATORY_COMPLIANCE = "Regulatory Compliance & Ethical Governance"
    SOCIAL_IMPACT = "Social Impact & Community (CSR)"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskType(str, Enum):
    REGULATORY = "regulatory"
    CUSTOMER_EXPERIENCE = "customer_experience"
    DIGITAL_TRUST = "digital_trust"
    BRAND_PERCEPTION = "brand_perception"


class RelevanceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    IRRELEVANT = "irrelevant"


# Driver → Sub-driver mapping
DRIVER_SUBDRIVERS = {
    ReputationDriver.BRAND_PERCEPTION: [
        SubDriver.THOUGHT_LEADERSHIP,
        SubDriver.PRODUCT_STRATEGY,
        SubDriver.BRAND_VISIBILITY,
    ],
    ReputationDriver.USER_EXPERIENCE: [
        SubDriver.PRODUCT_SERVICE_QUALITY,
        SubDriver.CUSTOMER_SUPPORT,
        SubDriver.DIGITAL_EXPERIENCE,
    ],
    ReputationDriver.RESPONSIBLE_BUSINESS: [
        SubDriver.REGULATORY_COMPLIANCE,
        SubDriver.SOCIAL_IMPACT,
    ],
}

# Reverse lookup: sub-driver → driver
SUBDRIVER_TO_DRIVER = {}
for driver, subs in DRIVER_SUBDRIVERS.items():
    for sub in subs:
        SUBDRIVER_TO_DRIVER[sub] = driver


# ──────────────────────────────────────────────
# Stage 1: Raw Mention (parsed from XLSX)
# ──────────────────────────────────────────────

class RawMention(BaseModel):
    """Direct representation of a single row from the dataset."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    row_number: int = Field(description="Original row number in XLSX (1-indexed, excl header)")

    date_raw: Optional[datetime.datetime] = None
    url: str
    source_name_raw: Optional[str] = None
    title_raw: Optional[str] = None
    opening_text_raw: Optional[str] = None
    hit_sentence_raw: Optional[str] = None
    sentiment_raw: Optional[str] = None
    reach_raw: Optional[int] = None

    class Config:
        use_enum_values = True


# ──────────────────────────────────────────────
# Stage 2: Cleaned Mention
# ──────────────────────────────────────────────

class CleanedMention(BaseModel):
    """After cleaning, standardization, and deduplication."""

    id: str
    row_number: int = Field(ge=1)

    # Cleaned fields
    date: Optional[datetime.date] = None
    url: str
    source_name: str                  # Inferred if missing
    source_type: SourceType
    title: str                        # Filled from opening_text if missing
    opening_text: Optional[str] = None
    hit_sentence: Optional[str] = None
    combined_text: str                # Merged text for analysis
    sentiment_original: Sentiment     # Normalized from raw
    reach: int = Field(default=0, ge=0)

    # Dedup metadata
    is_duplicate: bool = False
    duplicate_group_id: Optional[str] = None
    duplicate_method: Optional[str] = None  # "exact_url" | "fuzzy" | "semantic"

    # Relevance metadata
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance_level: RelevanceLevel = RelevanceLevel.HIGH
    relevance_reason: Optional[str] = None
    is_relevant: bool = True

    # Audit
    cleaning_notes: List[str] = Field(default_factory=list)

    # Classification (populated in classify stage)
    driver: Optional[str] = None
    sub_driver: Optional[str] = None
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_rationale: Optional[str] = None
    classification_method: Optional[str] = None

    # Sentiment (populated in sentiment stage)
    sentiment: Optional[str] = None
    sentiment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sentiment_explanation: Optional[str] = None
    sentiment_agreement: bool = True
    emotional_intensity: str = "medium"
    impact_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Risk & themes (populated in enrich stage)
    risk_level: Optional[str] = None
    risk_type: Optional[str] = None
    risk_signal: Optional[str] = None
    themes: List[str] = Field(default_factory=list)

    # Scoring (populated in score stage)
    reputation_contribution: Optional[float] = None

    @field_validator("risk_type", "risk_level", "risk_signal", "driver", "sub_driver",
                     "classification_rationale", "classification_method",
                     "sentiment_explanation", "relevance_reason", "duplicate_group_id",
                     mode="before")
    @classmethod
    def _coerce_null_string(cls, v: object) -> object:
        """Convert the literal string 'null' (from LLM/JSON artefacts) to None."""
        if isinstance(v, str) and v.strip().lower() == "null":
            return None
        return v

    @field_validator("driver", mode="before")
    @classmethod
    def _validate_driver(cls, v: object) -> object:
        if v is None:
            return v
        v_str = str(v).strip()
        valid = {"Brand Perception", "User Experience", "Responsible Business Practices"}
        if v_str and v_str not in valid:
            from app.models.mention import SUBDRIVER_TO_DRIVER
            parent = SUBDRIVER_TO_DRIVER.get(v_str)
            if parent:
                return parent.value if hasattr(parent, "value") else str(parent)
        return v

    @field_validator("sentiment", mode="before")
    @classmethod
    def _validate_sentiment(cls, v: object) -> object:
        if v is None:
            return v
        v_str = str(v).lower().strip()
        if v_str not in ("positive", "neutral", "negative"):
            return "neutral"
        return v_str

    @field_validator("risk_level", mode="before")
    @classmethod
    def _validate_risk_level(cls, v: object) -> object:
        if v is None:
            return v
        v_str = str(v).lower().strip()
        if v_str in ("null", "none", ""):
            return None
        if v_str not in ("low", "medium", "high"):
            return "low"
        return v_str

    @field_validator("emotional_intensity", mode="before")
    @classmethod
    def _validate_intensity(cls, v: object) -> str:
        v_str = str(v).lower().strip()
        if v_str not in ("low", "medium", "high"):
            return "medium"
        return v_str

    class Config:
        use_enum_values = True


# ──────────────────────────────────────────────
# Intelligence Sub-models
# ──────────────────────────────────────────────

class EmbeddingCandidate(BaseModel):
    """A candidate sub-driver from embedding similarity."""
    sub_driver: str
    similarity: float


class ClassificationResult(BaseModel):
    """Output of the classification engine."""
    driver: str
    sub_driver: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    method: str = "hybrid"  # "embedding_only" | "llm_only" | "hybrid"
    embedding_candidates: List[EmbeddingCandidate] = Field(default_factory=list)


class SentimentResult(BaseModel):
    """Output of the sentiment engine."""
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    emotional_intensity: str = "medium"  # "low" | "medium" | "high"
    original_sentiment: Sentiment
    agreement: bool = True  # Whether our analysis agrees with original label


class RiskAssessment(BaseModel):
    """Risk detection output."""
    risk_level: RiskLevel
    risk_type: Optional[RiskType] = None
    risk_signal: Optional[str] = None
    urgency: str = "informational"  # "informational" | "monitor" | "immediate"


class OpportunitySignal(BaseModel):
    """Opportunity detection output."""
    opportunity_type: str
    description: str
    amplification_potential: str = "medium"  # "low" | "medium" | "high"


# ──────────────────────────────────────────────
# Stage 3: Processed Mention (final)
# ──────────────────────────────────────────────

class ProcessedMention(BaseModel):
    """Fully processed mention with all intelligence layers applied."""

    id: str
    row_number: int = Field(ge=1)

    # Core fields
    date: Optional[datetime.date] = None
    url: str
    source_name: str
    source_type: SourceType
    title: str
    opening_text: Optional[str] = None
    hit_sentence: Optional[str] = None
    combined_text: str
    reach: int = Field(default=0, ge=0)

    # Dedup
    is_duplicate: bool = False
    duplicate_group_id: Optional[str] = None

    # Relevance
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance_level: RelevanceLevel = RelevanceLevel.HIGH
    is_relevant: bool = True

    # Classification
    driver: Optional[str] = None
    sub_driver: Optional[str] = None
    classification_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classification_rationale: Optional[str] = None
    classification_method: Optional[str] = None

    # Sentiment
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sentiment_explanation: Optional[str] = None
    sentiment_original: Sentiment = Sentiment.NEUTRAL
    sentiment_agreement: bool = True
    emotional_intensity: str = "medium"

    # Impact
    impact_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Risk
    risk_level: RiskLevel = RiskLevel.LOW
    risk_type: Optional[RiskType] = None
    risk_signal: Optional[str] = None

    # Themes
    themes: List[str] = Field(default_factory=list)

    # Score contribution
    reputation_contribution: float = 0.0

    @field_validator("risk_type", "risk_signal", "driver", "sub_driver",
                     "classification_rationale", "classification_method",
                     "sentiment_explanation", "duplicate_group_id",
                     mode="before")
    @classmethod
    def _coerce_null_string(cls, v: object) -> object:
        """Convert the literal string 'null' (from LLM/JSON artefacts) to None."""
        if isinstance(v, str) and v.strip().lower() == "null":
            return None
        return v

    class Config:
        use_enum_values = True


# ──────────────────────────────────────────────
# Analytics / Aggregate Models
# ──────────────────────────────────────────────

class Theme(BaseModel):
    """An extracted theme from the mention corpus."""
    theme_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    mention_count: int = Field(ge=0)
    mention_ids: List[str] = Field(default_factory=list)
    sentiment_skew: str  # "positive" | "negative" | "mixed"
    representative_quotes: List[str] = Field(default_factory=list)
    business_implication: str

    @field_validator("sentiment_skew", mode="before")
    @classmethod
    def _validate_sentiment_skew(cls, v: str) -> str:
        v_str = str(v).lower().strip()
        if v_str not in ("positive", "negative", "mixed", "neutral"):
            return "mixed"
        return v_str


class DriverScore(BaseModel):
    """Score for a single reputation driver."""
    driver: str
    score: float = Field(ge=0.0, le=100.0)
    sub_scores: dict = Field(default_factory=dict)  # sub_driver → score
    mention_count: int = Field(default=0, ge=0)
    positive_count: int = Field(default=0, ge=0)
    negative_count: int = Field(default=0, ge=0)
    neutral_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_sentiment_counts(self) -> "DriverScore":
        """pos + neg + neu must equal mention_count."""
        total = self.positive_count + self.negative_count + self.neutral_count
        if self.mention_count > 0 and total != self.mention_count:
            self.mention_count = total
        return self


class ReputationScore(BaseModel):
    """Aggregate reputation score with breakdown."""
    overall_score: float = Field(ge=0.0, le=100.0)
    driver_scores: List[DriverScore] = Field(default_factory=list)
    top_positive_driver: Optional[str] = None
    top_negative_driver: Optional[str] = None
    score_trend: Optional[str] = None  # "improving" | "stable" | "declining"
    methodology_note: str = "Weighted composite of sentiment, volume, reach, and source quality across reputation drivers."

    @field_validator("score_trend", mode="before")
    @classmethod
    def _validate_score_trend(cls, v: object) -> Optional[str]:
        if v is None:
            return v
        v_str = str(v).lower().strip()
        if v_str not in ("improving", "stable", "declining"):
            return None
        return v_str


class ExecutiveSummary(BaseModel):
    """Auto-generated executive brief."""
    brand_name: str
    period: str
    reputation_score: float
    total_mentions: int
    key_findings: List[str]
    top_positives: List[str]
    top_negatives: List[str]
    emerging_themes: List[str]
    recommended_actions: List[str]
    risk_alerts: List[str]


# ──────────────────────────────────────────────
# API Response Models
# ──────────────────────────────────────────────

class MentionResponse(BaseModel):
    """Single mention in API response."""
    id: str
    date: Optional[str] = None
    url: str
    source_name: str
    source_type: str
    title: str
    combined_text: str
    reach: int
    driver: Optional[str] = None
    sub_driver: Optional[str] = None
    classification_confidence: float = 0.0
    classification_rationale: Optional[str] = None
    sentiment: str
    sentiment_confidence: float = 0.0
    sentiment_explanation: Optional[str] = None
    impact_score: float = 0.0
    risk_level: str = "low"
    risk_type: Optional[str] = None
    themes: List[str] = Field(default_factory=list)


class OverviewResponse(BaseModel):
    """Dashboard overview data."""
    total_mentions: int
    reputation_score: float
    sentiment_distribution: dict  # {"positive": n, "neutral": n, "negative": n}
    driver_distribution: dict     # {"Brand Perception": n, ...}
    sub_driver_distribution: dict
    source_distribution: dict
    risk_summary: dict            # {"low": n, "medium": n, "high": n}
    mention_trend: List[dict]     # [{"date": "2025-07", "count": n}, ...]


class CommandCenterResponse(BaseModel):
    """Command center hero data."""
    reputation_score: float
    driver_scores: List[DriverScore]
    biggest_positive_driver: Optional[dict] = None
    biggest_negative_driver: Optional[dict] = None
    emerging_theme: Optional[dict] = None
    primary_risk: Optional[dict] = None
    recommended_actions: List[str] = Field(default_factory=list)
    score_waterfall: List[dict] = Field(default_factory=list)


class IntelligenceResponse(BaseModel):
    """Intelligence hub data."""
    executive_summary: Optional[ExecutiveSummary] = None
    themes: List[Theme] = Field(default_factory=list)
    risks: List[dict] = Field(default_factory=list)
    opportunities: List[dict] = Field(default_factory=list)
