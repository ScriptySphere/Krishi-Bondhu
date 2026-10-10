"""Recommendation generation service."""
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from loguru import logger

from ..models.crop import CropRotation
from ..models.soil import SoilProfile
from ..models.climate import ClimateSummary
from ..models.location import Location
from ..models.recommendation import (
    RotationRecommendation,
    RecommendationScore,
    Priority,
    RotationComparison,
)
from .rotation_service import RotationService
from .crop_service import CropService
from .soil_service import SoilService


class RecommendationService:
    """Service for generating prioritized rotation recommendations."""

    def __init__(
        self,
        rotation_service: Optional[RotationService] = None,
        crop_service: Optional[CropService] = None,
        soil_service: Optional[SoilService] = None,
    ):
        self.rotation_service = rotation_service or RotationService(soil_service=soil_service)
        self.crop_service = crop_service or CropService()
        self.soil_service = soil_service or SoilService()

    def generate_recommendations(
        self,
        location: Location,
        soil_profile: Optional[SoilProfile] = None,
        climate_summary: Optional[ClimateSummary] = None,
        priorities: Optional[List[Priority]] = None,
        years: int = 3,
        max_recommendations: int = 10,
    ) -> RotationComparison:
        """Generate prioritized rotation recommendations."""

        # Generate candidate rotations
        rotations = self.crop_service.generate_rotations(
            location_id=f"{location.latitude},{location.longitude}",
            years=years,
            include_cover_crops=True,
            include_legumes=True,
        )

        # Evaluate all rotations
        evaluations = self.rotation_service.compare_rotations(
            rotations, soil_profile, climate_summary, location
        )

        # Create recommendations with priority scoring
        recommendations = []
        for eval_result in evaluations[:max_recommendations]:
            # Find the rotation object
            rotation = next(r for r in rotations if r.name == eval_result["rotation_name"])

            rec = self._create_recommendation(
                rotation=rotation,
                evaluation=eval_result,
                soil_profile=soil_profile,
                climate_summary=climate_summary,
                priorities=priorities,
            )
            recommendations.append(rec)

        # Rank by each priority
        self._rank_by_priorities(recommendations, priorities)

        return RotationComparison(
            location_id=f"{location.latitude},{location.longitude}",
            recommendations=recommendations,
        )

    def _create_recommendation(
        self,
        rotation: CropRotation,
        evaluation: Dict,
        soil_profile: Optional[SoilProfile],
        climate_summary: Optional[ClimateSummary],
        priorities: Optional[List[Priority]],
    ) -> RotationRecommendation:
        """Create a recommendation from evaluation results."""

        # Calculate priority-specific scores
        priority_scores = []
        target_priorities = priorities or list(Priority)

        for priority in target_priorities:
            score = self._calculate_priority_score(
                priority, evaluation, rotation, soil_profile, climate_summary
            )
            priority_scores.append(RecommendationScore(
                rotation_id=rotation.name,
                priority=priority,
                score=score,
                details=self._get_priority_details(priority, evaluation, rotation),
            ))

        # Overall score is weighted by priorities
        if priorities:
            weights = {p: 1.0 / len(priorities) for p in priorities}
        else:
            weights = {p: 1.0 / len(Priority) for p in Priority}

        overall = sum(
            s.score * weights.get(s.priority, 0)
            for s in priority_scores
        )

        # Determine NASA data sources used
        nasa_sources = ["POWER"]
        if climate_summary:
            nasa_sources.extend(["MODIS", "SMAP", "GRACE"])

        return RotationRecommendation(
            rotation=rotation,
            overall_score=round(overall, 1),
            priority_scores=priority_scores,
            soil_health_assessment=evaluation["details"]["soil_health"],
            water_assessment=evaluation["details"]["water_use"],
            climate_resilience_assessment=evaluation["details"]["climate_resilience"],
            economic_assessment=evaluation["details"]["economic"],
            risk_assessment=self._assess_risks(rotation, climate_summary, soil_profile),
            nasa_data_sources=list(set(nasa_sources)),
            data_quality_flags=self._check_data_quality(climate_summary, soil_profile),
            generated_at=datetime.utcnow().isoformat() + "Z",
        )

    def _calculate_priority_score(
        self,
        priority: Priority,
        evaluation: Dict,
        rotation: CropRotation,
        soil_profile: Optional[SoilProfile],
        climate_summary: Optional[ClimateSummary],
    ) -> float:
        """Calculate score for a specific priority."""

        scores = evaluation["scores"]

        if priority == Priority.YIELD:
            # Weight economic and soil health
            return (
                scores.get("economic", 50) * 0.5 +
                scores.get("soil_health", 50) * 0.3 +
                scores.get("nutrient_balance", 50) * 0.2
            )

        elif priority == Priority.WATER_CONSERVATION:
            # Weight water use and drought tolerance
            return (
                scores.get("water_use", 50) * 0.6 +
                scores.get("climate_resilience", 50) * 0.4
            )

        elif priority == Priority.SOIL_HEALTH:
            # Weight soil health, diversity, nutrient balance
            return (
                scores.get("soil_health", 50) * 0.5 +
                scores.get("diversity", 50) * 0.3 +
                scores.get("nutrient_balance", 50) * 0.2
            )

        elif priority == Priority.RISK_REDUCTION:
            # Weight pest break, climate resilience, diversity
            return (
                scores.get("pest_break", 50) * 0.4 +
                scores.get("climate_resilience", 50) * 0.4 +
                scores.get("diversity", 50) * 0.2
            )

        elif priority == Priority.PROFITABILITY:
            # Weight economic, yield potential
            return (
                scores.get("economic", 50) * 0.7 +
                scores.get("soil_health", 50) * 0.3
            )

        elif priority == Priority.CLIMATE_ADAPTATION:
            # Weight climate resilience, water use, diversity
            return (
                scores.get("climate_resilience", 50) * 0.5 +
                scores.get("water_use", 50) * 0.3 +
                scores.get("diversity", 50) * 0.2
            )

        return evaluation["overall_score"]

    def _get_priority_details(
        self,
        priority: Priority,
        evaluation: Dict,
        rotation: CropRotation,
    ) -> Dict:
        """Get detailed breakdown for a priority."""
        details = {}

        if priority == Priority.YIELD:
            details = {
                "soil_health_contribution": evaluation["scores"].get("soil_health"),
                "nutrient_availability": evaluation["scores"].get("nutrient_balance"),
                "economic_potential": evaluation["scores"].get("economic"),
            }
        elif priority == Priority.WATER_CONSERVATION:
            details = {
                "water_use_efficiency": evaluation["scores"].get("water_use"),
                "drought_resilience": evaluation["scores"].get("climate_resilience"),
                "avg_drought_tolerance": evaluation["details"]["water_use"].get("avg_drought_tolerance"),
            }
        elif priority == Priority.SOIL_HEALTH:
            details = {
                "soil_health_index": evaluation["scores"].get("soil_health"),
                "crop_diversity": evaluation["scores"].get("diversity"),
                "nitrogen_balance": evaluation["scores"].get("nutrient_balance"),
                "legume_present": rotation.has_legume,
                "cover_crop_present": rotation.has_cover_crop,
            }
        elif priority == Priority.RISK_REDUCTION:
            details = {
                "pest_break_value": evaluation["scores"].get("pest_break"),
                "climate_resilience": evaluation["scores"].get("climate_resilience"),
                "crop_diversity": evaluation["scores"].get("diversity"),
                "crop_families": evaluation["details"]["pest_break"].get("crop_families_represented"),
            }
        elif priority == Priority.PROFITABILITY:
            details = {
                "economic_score": evaluation["scores"].get("economic"),
                "avg_profit": evaluation["details"]["economic"].get("avg_annual_profit_usd_ha"),
                "soil_health": evaluation["scores"].get("soil_health"),
            }
        elif priority == Priority.CLIMATE_ADAPTATION:
            details = {
                "climate_resilience": evaluation["scores"].get("climate_resilience"),
                "water_use": evaluation["scores"].get("water_use"),
                "diversity": evaluation["scores"].get("diversity"),
                "heat_tolerant_crops": evaluation["details"]["climate_resilience"].get("heat_tolerant_crops"),
                "drought_tolerant_crops": evaluation["details"]["climate_resilience"].get("drought_tolerant_crops"),
            }

        return details

    def _rank_by_priorities(
        self,
        recommendations: List[RotationRecommendation],
        priorities: Optional[List[Priority]],
    ):
        """Rank recommendations by each priority."""
        target_priorities = priorities or list(Priority)

        for priority in target_priorities:
            scored = [r for r in recommendations if r.get_score(priority) is not None]
            scored.sort(key=lambda r: r.get_score(priority), reverse=True)

            for rank, rec in enumerate(scored, 1):
                for ps in rec.priority_scores:
                    if ps.priority == priority:
                        ps.rank = rank
                        break

    def _assess_risks(
        self,
        rotation: CropRotation,
        climate_summary: Optional[ClimateSummary],
        soil_profile: Optional[SoilProfile],
    ) -> Dict:
        """Assess risks for a rotation."""
        risks = {
            "climate_risks": [],
            "soil_risks": [],
            "market_risks": [],
            "management_risks": [],
        }

        # Climate risks
        if climate_summary:
            if climate_summary.heat_stress_days and climate_summary.heat_stress_days > 10:
                heat_tolerant = any(c.characteristics.max_temp_c > 35 for c in rotation.crops)
                if not heat_tolerant:
                    risks["climate_risks"].append("High heat stress risk - no heat-tolerant crops")

            if climate_summary.frost_days and climate_summary.frost_days > 5:
                frost_tolerant = any(c.characteristics.frost_tolerance_c < -5 for c in rotation.crops)
                if not frost_tolerant:
                    risks["climate_risks"].append("Frost risk - limited frost tolerance")

            if climate_summary.aridity_index and climate_summary.aridity_index > 2.0:
                risks["climate_risks"].append("Arid conditions - irrigation likely required")

        # Soil risks
        if soil_profile:
            if soil_profile.average_ph and (soil_profile.average_ph < 5.0 or soil_profile.average_ph > 8.0):
                risks["soil_risks"].append(f"Extreme pH ({soil_profile.average_ph}) may limit crop options")

            if soil_profile.total_organic_carbon < 10:
                risks["soil_risks"].append("Very low organic carbon - soil degradation risk")

            if soil_profile.drainage_class and "poorly" in soil_profile.drainage_class.lower():
                risks["soil_risks"].append("Poor drainage - waterlogging risk")

        # Market risks
        for crop in rotation.crops:
            if crop.characteristics.market_value_usd_ton is None:
                risks["market_risks"].append(f"No market price data for {crop.characteristics.name}")

        # Management risks
        if not rotation.has_legume:
            risks["management_risks"].append("No legume in rotation - N fertilizer dependency")

        if rotation.years < 3:
            risks["management_risks"].append("Short rotation - limited pest break benefits")

        return risks

    def _check_data_quality(
        self,
        climate_summary: Optional[ClimateSummary],
        soil_profile: Optional[SoilProfile],
    ) -> List[str]:
        """Check data quality flags."""
        flags = []

        if climate_summary is None:
            flags.append("No climate data available")

        if soil_profile is None:
            flags.append("No soil profile data available")

        if climate_summary and climate_summary.total_precipitation is None:
            flags.append("Missing precipitation data")

        if soil_profile and soil_profile.average_ph is None:
            flags.append("Missing soil pH data")

        return flags

    def format_recommendation_summary(
        self,
        comparison: RotationComparison,
        top_n: int = 5,
    ) -> str:
        """Format recommendations as a summary table."""
        lines = [
            f"Crop Rotation Recommendations for {comparison.location_id}",
            "=" * 70,
            "",
        ]

        # Best overall
        best = comparison.best_overall
        lines.append(f"BEST OVERALL: {best.rotation.name} (Score: {best.overall_score})")
        lines.append(f"  Crops: {' → '.join(c.characteristics.name for c in best.rotation.crops)}")
        lines.append("")

        # Best by priority
        lines.append("BEST BY PRIORITY:")
        lines.append("-" * 40)
        for priority, rec in comparison.best_by_priority.items():
            score = rec.get_score(priority)
            lines.append(f"  {priority.value}: {rec.rotation.name} ({score:.1f})")

        lines.append("")

        # Full comparison table
        lines.append(f"TOP {top_n} ROTATIONS:")
        lines.append("-" * 70)

        table_data = comparison.summary_table()[:top_n]
        header = f"{'Rank':<4} {'Rotation':<25} {'Overall':<7} {'Yield':<6} {'Water':<6} {'Soil':<6} {'Risk':<6} {'Profit':<6} {'Climate':<7}"
        lines.append(header)
        lines.append("-" * 70)

        for row in table_data:
            line = (
                f"{row.get('rank', ''):<4} "
                f"{row['rotation'][:24]:<25} "
                f"{row['overall_score']:<7.1f} "
                f"{row.get(Priority.YIELD.value, 'N/A'):<6.1f} "
                f"{row.get(Priority.WATER_CONSERVATION.value, 'N/A'):<6.1f} "
                f"{row.get(Priority.SOIL_HEALTH.value, 'N/A'):<6.1f} "
                f"{row.get(Priority.RISK_REDUCTION.value, 'N/A'):<6.1f} "
                f"{row.get(Priority.PROFITABILITY.value, 'N/A'):<6.1f} "
                f"{row.get(Priority.CLIMATE_ADAPTATION.value, 'N/A'):<7.1f}"
            )
            lines.append(line)

        return "\n".join(lines)

    def export_recommendations(
        self,
        comparison: RotationComparison,
        output_path: Path,
        format: str = "json",
    ):
        """Export recommendations to file."""
        if format == "json":
            import json
            with open(output_path, "w") as f:
                json.dump(comparison.model_dump(), f, indent=2, default=str)
        elif format == "csv":
            import pandas as pd
            df = pd.DataFrame(comparison.summary_table())
            df.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported recommendations to {output_path}")