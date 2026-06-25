"""
Structured output schemas for all LLM tasks.

Every provider must return responses that validate against these models.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Valid top-level drivers
_VALID_DRIVERS = {
    "Brand Perception",
    "User Experience",
    "Responsible Business Practices",
}

# Sub-driver → parent driver mapping (mirrors models/mention.py SUBDRIVER_TO_DRIVER)
_SUBDRIVER_TO_DRIVER = {
    "Thought Leadership": "Brand Perception",
    "Product Strategy": "Brand Perception",
    "Brand Visibility & Marketing": "Brand Perception",
    "Product & Service Quality": "User Experience",
    "Customer Support & Complaint Resolution": "User Experience",
    "Digital & Omnichannel Experience": "User Experience",
    "Regulatory Compliance & Ethical Governance": "Responsible Business Practices",
    "Social Impact & Community (CSR)": "Responsible Business Practices",
}


class ClassificationResult(BaseModel):
    driver: str
    sub_driver: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def fix_driver_hierarchy(self) -> "ClassificationResult":
        """
        The LLM sometimes returns a sub-driver name in the driver field.
        If driver is not a valid top-level driver but matches a known sub-driver,
        promote it: set driver to the correct parent and preserve sub_driver.
        """
        if self.driver not in _VALID_DRIVERS:
            parent = _SUBDRIVER_TO_DRIVER.get(self.driver)
            if parent:
                self.sub_driver = self.driver
                self.driver = parent
            else:
                parent = _SUBDRIVER_TO_DRIVER.get(self.sub_driver, "Brand Perception")
                self.driver = parent

        # Validate sub_driver belongs to the resolved driver
        if self.sub_driver in _SUBDRIVER_TO_DRIVER:
            expected_parent = _SUBDRIVER_TO_DRIVER[self.sub_driver]
            if expected_parent != self.driver:
                self.driver = expected_parent
        return self

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


_VALID_SENTIMENTS = {"positive", "neutral", "negative"}
_VALID_INTENSITIES = {"low", "medium", "high"}


class SentimentResult(BaseModel):
    sentiment: str = Field(description="positive | neutral | negative")
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1)
    emotional_intensity: str = "medium"

    @field_validator("sentiment", mode="before")
    @classmethod
    def normalize_sentiment(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v not in _VALID_SENTIMENTS:
            return "neutral"
        return v

    @field_validator("emotional_intensity", mode="before")
    @classmethod
    def normalize_intensity(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v not in _VALID_INTENSITIES:
            return "medium"
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class RelevanceResult(BaseModel):
    relevance_score: float = Field(ge=0.0, le=1.0)
    relevance_level: str  # high | medium | low | irrelevant
    reason: str

    @field_validator("relevance_score", mode="before")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @field_validator("relevance_level", mode="before")
    @classmethod
    def normalize_level(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v not in ("high", "medium", "low", "irrelevant"):
            return "medium"
        return v


_VALID_RISK_LEVELS = {"low", "medium", "high"}
_VALID_RISK_TYPES = {
    "regulatory", "customer_experience", "digital_trust", "brand_perception",
}
_VALID_URGENCIES = {"informational", "monitor", "immediate"}


class RiskResult(BaseModel):
    risk_level: str = Field(description="low | medium | high")
    risk_type: Optional[str] = None
    risk_signal: Optional[str] = None
    urgency: str = "informational"

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v not in _VALID_RISK_LEVELS:
            return "low"
        return v

    @field_validator("risk_type", mode="before")
    @classmethod
    def normalize_risk_type(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).lower().strip().replace(" ", "_").replace("-", "_")
        if v_str in ("null", "none", "n/a", ""):
            return None
        if v_str not in _VALID_RISK_TYPES:
            return None
        return v_str

    @field_validator("urgency", mode="before")
    @classmethod
    def normalize_urgency(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v not in _VALID_URGENCIES:
            return "informational"
        return v


_VALID_SENTIMENT_SKEWS = {"positive", "negative", "mixed", "neutral"}


class ThemeItem(BaseModel):
    theme_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    mention_count: int = Field(default=0, ge=0)
    sentiment_skew: str = "mixed"
    representative_quotes: List[str] = Field(default_factory=list)
    business_implication: str = ""

    @field_validator("sentiment_skew", mode="before")
    @classmethod
    def normalize_sentiment_skew(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v not in _VALID_SENTIMENT_SKEWS:
            return "mixed"
        return v


class ThemeResult(BaseModel):
    themes: List[ThemeItem]


class SummaryResult(BaseModel):
    key_findings: List[str] = Field(default_factory=list, min_length=1)
    top_positives: List[str] = Field(default_factory=list, min_length=1)
    top_negatives: List[str] = Field(default_factory=list)
    emerging_themes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list, min_length=1)
    risk_alerts: List[str] = Field(default_factory=list)
