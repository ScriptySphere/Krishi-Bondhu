"""Crop rotation analysis and evaluation service."""
from typing import Dict, List, Optional
from datetime import date

import pandas as pd
from loguru import logger

from ..models.crop import CropRotation, CropCharacteristics, CropType
from ..models.soil import SoilProfile
from ..models.climate import ClimateSummary
from ..models.location import Location
from .soil_service import SoilService
from .climate_service import ClimateService


class RotationService:
    """Service for evaluating and comparing crop rotations."""

    def __init__(
        self,
        soil_service: Optional[SoilService] = None,
        climate_service: Optional[ClimateService] = None,
    ):
        self.soil_service = soil_service or SoilService()
        self.climate_service = climate_service or ClimateService()

    def evaluate_rotation(
        self,
        rotation: CropRotation,
        soil_profile: Optional[SoilProfile] = None,
        climate_summary: Optional[ClimateSummary] = None,
        location: Optional[Location] = None,
    ) -> Dict:
        """Comprehensive evaluation of a crop rotation."""
        evaluation = {
            "rotation_name": rotation.name,
            "years": rotation.years,
            "crops": [c.characteristics.name for c in rotation.crops],
            "scores": {},
            "details": {},
        }

        # Soil health evaluation
        evaluation["scores"]["soil_health"] = self._evaluate_soil_health(rotation, soil_profile)
        evaluation["details"]["soil_health"] = self._soil_health_details(rotation, soil_profile)

        # Nutrient balance evaluation
        evaluation["scores"]["nutrient_balance"] = self._evaluate_nutrient_balance(rotation)
        evaluation["details"]["nutrient_balance"] = self._nutrient_balance_details(rotation)

        # Water use evaluation
        evaluation["scores"]["water_use"] = self._evaluate_water_use(rotation, climate_summary)
        evaluation["details"]["water_use"] = self._water_use_details(rotation, climate_summary)

        # Pest/disease break evaluation
        evaluation["scores"]["pest_break"] = self._evaluate_pest_break(rotation)
        evaluation["details"]["pest_break"] = self._pest_break_details(rotation)

        # Diversity evaluation
        evaluation["scores"]["diversity"] = self._evaluate_diversity(rotation)
        evaluation["details"]["diversity"] = {"shannon_index": round(rotation.diversity_index(), 2)}

        # Climate resilience
        evaluation["scores"]["climate_resilience"] = self._evaluate_climate_resilience(rotation, climate_summary)
        evaluation["details"]["climate_resilience"] = self._climate_resilience_details(rotation, climate_summary)

        # Economic evaluation
        evaluation["scores"]["economic"] = self._evaluate_economics(rotation)
        evaluation["details"]["economic"] = self._economic_details(rotation)

        # Overall score (weighted average)
        weights = {
            "soil_health": 0.25,
            "nutrient_balance": 0.15,
            "water_use": 0.20,
            "pest_break": 0.15,
            "diversity": 0.10,
            "climate_resilience": 0.10,
            "economic": 0.05,
        }

        overall = sum(
            evaluation["scores"][k] * weights[k]
            for k in weights
            if k in evaluation["scores"]
        )
        evaluation["overall_score"] = round(overall, 1)

        return evaluation

    def _evaluate_soil_health(self, rotation: CropRotation, soil_profile: Optional[SoilProfile]) -> float:
        """Evaluate rotation impact on soil health."""
        base_score = 50

        # Soil health index from crops
        avg_shi = rotation.average_soil_health_index
        base_score += avg_shi * 15  # Each point of SHI = 15 points

        # Legume presence
        if rotation.has_legume:
            base_score += 10

        # Cover crop presence
        if rotation.has_cover_crop:
            base_score += 10

        # Perennial/deep rooted crops
        deep_rooted = sum(1 for c in rotation.crops if c.characteristics.root_depth_cm > 100)
        base_score += deep_rooted * 5

        # Diversity bonus
        diversity = rotation.diversity_index()
        base_score += diversity * 5

        # Soil profile adjustments
        if soil_profile:
            if soil_profile.total_organic_carbon < 15:
                base_score -= 5  # Harder to build soil
            if soil_profile.average_ph and (soil_profile.average_ph < 5.5 or soil_profile.average_ph > 7.5):
                base_score -= 5

        return max(0, min(100, base_score))

    def _soil_health_details(self, rotation: CropRotation, soil_profile: Optional[SoilProfile]) -> Dict:
        details = {
            "average_soil_health_index": round(rotation.average_soil_health_index, 2),
            "has_legume": rotation.has_legume,
            "has_cover_crop": rotation.has_cover_crop,
            "deep_rooted_crops": sum(1 for c in rotation.crops if c.characteristics.root_depth_cm > 100),
            "total_n_balance_kg_ha": rotation.total_nitrogen_balance,
            "crop_residue_cn_ratios": [c.characteristics.residue_cn_ratio for c in rotation.crops],
        }

        if soil_profile:
            details["current_soc_t_ha"] = soil_profile.total_organic_carbon
            details["current_ph"] = soil_profile.average_ph
            details["estimated_soc_change"] = self._estimate_soc_change(rotation, soil_profile)

        return details

    def _estimate_soc_change(self, rotation: CropRotation, soil_profile: SoilProfile) -> float:
        """Estimate annual SOC change (t/ha/yr)."""
        # Simplified: residue C input - decomposition
        total_residue_c = sum(
            c.characteristics.biomass_kg_ha * 0.4 / c.characteristics.residue_cn_ratio * 10
            for c in rotation.crops
        )  # Rough C input

        # Decomposition rate depends on climate, tillage, etc.
        # Simplified: assume 2% of SOC mineralized per year
        current_soc = soil_profile.total_organic_carbon
        mineralization = current_soc * 0.02

        # Net change per year (averaged over rotation)
        net_change = (total_residue_c / rotation.years - mineralization) / 1000  # Convert to t/ha

        return round(net_change, 2)

    def _evaluate_nutrient_balance(self, rotation: CropRotation) -> float:
        """Evaluate nutrient balance (focus on N)."""
        n_balance = rotation.total_nitrogen_balance

        # Optimal slight positive balance (some N carryover)
        if 0 <= n_balance <= 50:
            return 90
        elif -50 <= n_balance < 0:
            return 70
        elif 50 < n_balance <= 100:
            return 75
        elif n_balance > 100:
            return 50  # Excess N risk
        else:
            return 40  # Large deficit

    def _nutrient_balance_details(self, rotation: CropRotation) -> Dict:
        n_balance = rotation.total_nitrogen_balance
        p_uptake = sum(c.characteristics.p_uptake_kg_ha for c in rotation.crops)
        k_uptake = sum(c.characteristics.k_uptake_kg_ha for c in rotation.crops)

        return {
            "total_n_balance_kg_ha": n_balance,
            "total_p_uptake_kg_ha": p_uptake,
            "total_k_uptake_kg_ha": k_uptake,
            "avg_n_per_year": round(n_balance / rotation.years, 1),
            "legume_n_contribution": sum(
                c.characteristics.n_fixation_kg_ha for c in rotation.crops if c.characteristics.crop_type == CropType.LEGUME
            ),
            "assessment": "positive" if n_balance > 0 else "negative",
        }

    def _evaluate_water_use(self, rotation: CropRotation, climate_summary: Optional[ClimateSummary]) -> float:
        """Evaluate water use efficiency and risk."""
        base_score = 70

        if not climate_summary:
            return base_score

        total_water_need = sum(c.characteristics.water_requirement_mm for c in rotation.crops)
        avg_annual_need = total_water_need / rotation.years

        precip = climate_summary.total_precipitation or 0
        pet = climate_summary.total_pet or 0

        if precip > 0:
            satisfaction = precip / avg_annual_need
            if satisfaction >= 1.0:
                base_score += 20
            elif satisfaction >= 0.7:
                base_score += 10
            elif satisfaction >= 0.5:
                base_score += 0
            else:
                base_score -= 20

        # Drought tolerance of crops
        avg_drought_tol = sum(c.characteristics.drought_tolerance for c in rotation.crops) / len(rotation.crops)
        base_score += (avg_drought_tol - 3) * 5

        # Aridity index
        if climate_summary.aridity_index:
            ai = climate_summary.aridity_index
            if ai < 0.5:
                base_score += 10
            elif ai < 1.0:
                base_score += 5
            elif ai > 2.0:
                base_score -= 15

        return max(0, min(100, base_score))

    def _water_use_details(self, rotation: CropRotation, climate_summary: Optional[ClimateSummary]) -> Dict:
        total_need = sum(c.characteristics.water_requirement_mm for c in rotation.crops)
        details = {
            "total_rotation_water_need_mm": total_need,
            "avg_annual_need_mm": round(total_need / rotation.years, 1),
            "crop_water_needs": {c.characteristics.name: c.characteristics.water_requirement_mm for c in rotation.crops},
            "avg_drought_tolerance": round(
                sum(c.characteristics.drought_tolerance for c in rotation.crops) / len(rotation.crops), 1
            ),
        }

        if climate_summary:
            details["annual_precipitation_mm"] = climate_summary.total_precipitation
            details["annual_pet_mm"] = climate_summary.total_pet
            details["aridity_index"] = climate_summary.aridity_index

            if climate_summary.total_precipitation:
                details["precip_satisfaction_ratio"] = round(
                    climate_summary.total_precipitation / (total_need / rotation.years), 2
                )

        return details

    def _evaluate_pest_break(self, rotation: CropRotation) -> float:
        """Evaluate pest/disease cycle breaking."""
        base_score = 50

        # Sum of pest break values
        total_break = sum(c.characteristics.pest_break_value for c in rotation.crops)
        base_score += total_break * 5

        # Crop type alternation bonus
        crop_types = [c.characteristics.crop_type for c in rotation.crops]
        transitions = sum(1 for i in range(1, len(crop_types)) if crop_types[i] != crop_types[i-1])
        base_score += transitions * 5

        # Non-host crops for major pests
        # Simplified: different families break cycles
        families = set()
        for c in rotation.crops:
            if c.characteristics.crop_type == CropType.CEREAL:
                families.add("poaceae")
            elif c.characteristics.crop_type == CropType.LEGUME:
                families.add("fabaceae")
            elif c.characteristics.crop_type == CropType.OILSEED:
                families.add("brassicaceae")
            elif c.characteristics.crop_type == CropType.ROOT_TUBER:
                families.add("solanaceae")

        base_score += len(families) * 5

        return max(0, min(100, base_score))

    def _pest_break_details(self, rotation: CropRotation) -> Dict:
        crop_types = [c.characteristics.crop_type for c in rotation.crops]
        transitions = sum(1 for i in range(1, len(crop_types)) if crop_types[i] != crop_types[i-1])

        return {
            "total_pest_break_value": sum(c.characteristics.pest_break_value for c in rotation.crops),
            "crop_type_transitions": transitions,
            "unique_crop_types": len(set(crop_types)),
            "crop_families_represented": list(set(
                "poaceae" if c.characteristics.crop_type == CropType.CEREAL else
                "fabaceae" if c.characteristics.crop_type == CropType.LEGUME else
                "brassicaceae" if c.characteristics.crop_type == CropType.OILSEED else
                "solanaceae" if c.characteristics.crop_type == CropType.ROOT_TUBER else
                c.characteristics.crop_type.value
                for c in rotation.crops
            )),
        }

    def _evaluate_diversity(self, rotation: CropRotation) -> float:
        """Evaluate crop diversity."""
        diversity = rotation.diversity_index()
        max_diversity = 2.0  # Theoretical max for 4 types
        return min(100, diversity / max_diversity * 100)

    def _evaluate_climate_resilience(self, rotation: CropRotation, climate_summary: Optional[ClimateSummary]) -> float:
        """Evaluate climate resilience of rotation."""
        base_score = 60

        if not climate_summary:
            return base_score

        # Heat stress resilience
        heat_stress_days = climate_summary.heat_stress_days or 0
        heat_tolerant_crops = sum(1 for c in rotation.crops if c.characteristics.max_temp_c > 35)
        if heat_stress_days > 10 and heat_tolerant_crops > 0:
            base_score += 15
        elif heat_stress_days > 10:
            base_score -= 10

        # Drought resilience
        drought_tol = sum(c.characteristics.drought_tolerance for c in rotation.crops) / len(rotation.crops)
        base_score += (drought_tol - 3) * 5

        # Frost resilience
        frost_days = climate_summary.frost_days or 0
        frost_tolerant = sum(1 for c in rotation.crops if c.characteristics.frost_tolerance_c < -5)
        if frost_days > 5 and frost_tolerant > 0:
            base_score += 10
        elif frost_days > 5:
            base_score -= 10

        # Diversity provides resilience
        base_score += rotation.diversity_index() * 5

        return max(0, min(100, base_score))

    def _climate_resilience_details(self, rotation: CropRotation, climate_summary: Optional[ClimateSummary]) -> Dict:
        details = {
            "heat_tolerant_crops": [c.characteristics.name for c in rotation.crops if c.characteristics.max_temp_c > 35],
            "drought_tolerant_crops": [c.characteristics.name for c in rotation.crops if c.characteristics.drought_tolerance >= 4],
            "frost_tolerant_crops": [c.characteristics.name for c in rotation.crops if c.characteristics.frost_tolerance_c < -5],
            "avg_drought_tolerance": round(
                sum(c.characteristics.drought_tolerance for c in rotation.crops) / len(rotation.crops), 1
            ),
        }

        if climate_summary:
            details["heat_stress_days"] = climate_summary.heat_stress_days
            details["frost_days"] = climate_summary.frost_days

        return details

    def _evaluate_economics(self, rotation: CropRotation) -> float:
        """Evaluate economic potential."""
        base_score = 50

        revenues = []
        costs = []

        for crop in rotation.crops:
            if crop.characteristics.market_value_usd_ton and crop.characteristics.production_cost_usd_ha:
                # Estimate yield (simplified)
                yield_est = crop.characteristics.biomass_kg_ha * 0.4 / 1000  # Rough grain yield
                revenue = yield_est * crop.characteristics.market_value_usd_ton
                revenues.append(revenue)
                costs.append(crop.characteristics.production_cost_usd_ha)

        if revenues and costs:
            avg_profit = sum(r - c for r, c in zip(revenues, costs)) / len(revenues)
            if avg_profit > 500:
                base_score += 30
            elif avg_profit > 200:
                base_score += 15
            elif avg_profit > 0:
                base_score += 5
            else:
                base_score -= 20

        return max(0, min(100, base_score))

    def _economic_details(self, rotation: CropRotation) -> Dict:
        revenues = []
        costs = []

        for crop in rotation.crops:
            if crop.characteristics.market_value_usd_ton and crop.characteristics.production_cost_usd_ha:
                yield_est = crop.characteristics.biomass_kg_ha * 0.4 / 1000
                revenue = yield_est * crop.characteristics.market_value_usd_ton
                revenues.append(revenue)
                costs.append(crop.characteristics.production_cost_usd_ha)

        return {
            "avg_annual_revenue_usd_ha": round(sum(revenues) / len(revenues), 0) if revenues else None,
            "avg_annual_cost_usd_ha": round(sum(costs) / len(costs), 0) if costs else None,
            "avg_annual_profit_usd_ha": round(sum(r - c for r, c in zip(revenues, costs)) / len(revenues), 0)
                if revenues and costs else None,
            "crop_economics": [
                {
                    "crop": c.characteristics.name,
                    "est_yield_t_ha": round(c.characteristics.biomass_kg_ha * 0.4 / 1000, 1),
                    "market_value_usd_t": c.characteristics.market_value_usd_ton,
                    "cost_usd_ha": c.characteristics.production_cost_usd_ha,
                }
                for c in rotation.crops
                if c.characteristics.market_value_usd_ton and c.characteristics.production_cost_usd_ha
            ],
        }

    def compare_rotations(
        self,
        rotations: List[CropRotation],
        soil_profile: Optional[SoilProfile] = None,
        climate_summary: Optional[ClimateSummary] = None,
        location: Optional[Location] = None,
    ) -> List[Dict]:
        """Compare multiple rotations."""
        evaluations = []
        for rotation in rotations:
            eval_result = self.evaluate_rotation(rotation, soil_profile, climate_summary, location)
            evaluations.append(eval_result)

        # Sort by overall score
        evaluations.sort(key=lambda x: x["overall_score"], reverse=True)

        # Add ranks
        for i, eval_result in enumerate(evaluations):
            eval_result["rank"] = i + 1

        return evaluations

    def generate_rotation_report(
        self,
        rotation: CropRotation,
        soil_profile: Optional[SoilProfile] = None,
        climate_summary: Optional[ClimateSummary] = None,
        location: Optional[Location] = None,
    ) -> str:
        """Generate human-readable rotation report."""
        eval_result = self.evaluate_rotation(rotation, soil_profile, climate_summary, location)

        lines = [
            f"Crop Rotation Evaluation: {rotation.name}",
            "=" * 50,
            f"Location: {location}" if location else "",
            f"Rotation Length: {rotation.years} years",
            f"Crops: {' → '.join(c.characteristics.name for c in rotation.crops)}",
            "",
            f"Overall Score: {eval_result['overall_score']}/100",
            "",
            "Component Scores:",
            "-" * 30,
        ]

        for component, score in eval_result["scores"].items():
            lines.append(f"  {component.replace('_', ' ').title()}: {score}/100")

        lines.extend(["", "Details:", "-" * 30])

        # Key details
        soil_details = eval_result["details"]["soil_health"]
        lines.append(f"  Soil Health Index: {soil_details['average_soil_health_index']}")
        lines.append(f"  Total N Balance: {soil_details['total_n_balance_kg_ha']} kg/ha")
        lines.append(f"  Has Legume: {soil_details['has_legume']}")
        lines.append(f"  Has Cover Crop: {soil_details['has_cover_crop']}")

        water_details = eval_result["details"]["water_use"]
        lines.append(f"  Avg Annual Water Need: {water_details['avg_annual_need_mm']} mm")
        lines.append(f"  Avg Drought Tolerance: {water_details['avg_drought_tolerance']}")

        pest_details = eval_result["details"]["pest_break"]
        lines.append(f"  Pest Break Value: {pest_details['total_pest_break_value']}")
        lines.append(f"  Crop Families: {', '.join(pest_details['crop_families_represented'])}")

        econ_details = eval_result["details"]["economic"]
        if econ_details["avg_annual_profit_usd_ha"]:
            lines.append(f"  Est. Annual Profit: ${econ_details['avg_annual_profit_usd_ha']}/ha")

        return "\n".join(line for line in lines if line)