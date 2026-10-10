"""Recommendation and scoring models."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from ..models.crop import CropRotation, CropType


class Priority(str, Enum):
    """Farmer priority weights."""
    YIELD = "yield"
    WATER_CONSERVATION = "water_conservation"
    SOIL_HEALTH = "soil_health"
    RISK_REDUCTION = "risk_reduction"
    PROFITABILITY = "profitability"
    CLIMATE_ADAPTATION = "climate_adaptation"


class RecommendationScore(BaseModel):
    """Scored evaluation of a rotation against criteria."""
    rotation_id: str
    priority: Priority
    score: float = Field(..., ge=0, le=100, description="0-100 score")
    details: Dict[str, Any] = Field(default_factory=dict)
    rank: Optional[int] = None


class RotationRecommendation(BaseModel):
    """Complete recommendation for a crop rotation."""
    rotation: CropRotation
    overall_score: float = Field(..., ge=0, le=100)
    priority_scores: List[RecommendationScore] = Field(default_factory=list)

  
    soil_health_assessment: Dict[str, Any] = Field(default_factory=dict)
    water_assessment: Dict[str, Any] = Field(default_factory=dict)
    climate_resilience_assessment: Dict[str, Any] = Field(default_factory=dict)
    economic_assessment: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)


    nasa_data_sources: List[str] = Field(default_factory=list)
    data_quality_flags: List[str] = Field(default_factory=list)


    generated_at: str = Field(..., description="ISO timestamp")
    version: str = "1.0"

    @property
    def priority_ranking(self) -> Dict[Priority, int]:
        return {s.priority: s.rank for s in self.priority_scores if s.rank}

    def get_score(self, priority: Priority) -> Optional[float]:
        for s in self.priority_scores:
            if s.priority == priority:
                return s.score
        return None


class RotationComparison(BaseModel):
    """Comparison of multiple rotation options."""
    location_id: str
    recommendations: List[RotationRecommendation] = Field(..., min_length=2)
    baseline_rotation: Optional[CropRotation] = None

    @property
    def best_overall(self) -> RotationRecommendation:
        return max(self.recommendations, key=lambda r: r.overall_score)

    @property
    def best_by_priority(self) -> Dict[Priority, RotationRecommendation]:
        result = {}
        for priority in Priority:
            scored = [r for r in self.recommendations if r.get_score(priority) is not None]
            if scored:
                result[priority] = max(scored, key=lambda r: r.get_score(priority))
        return result

    def summary_table(self) -> List[Dict[str, Any]]:
        """Generate comparison table data."""
        rows = []
        for rec in self.recommendations:
            row = {
                "rotation": rec.rotation.name,
                "overall_score": rec.overall_score,
                "years": rec.rotation.years,
                "crops": " → ".join(c.characteristics.name for c in rec.rotation.crops),
                "has_legume": rec.rotation.has_legume,
                "has_cover_crop": rec.rotation.has_cover_crop,
                "diversity": round(rec.rotation.diversity_index(), 2),
            }
            for priority in Priority:
                row[priority.value] = rec.get_score(priority)
            rows.append(row)
        return sorted(rows, key=lambda x: x["overall_score"], reverse=True)