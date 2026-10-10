"""Soil analysis service."""
from typing import Dict, List, Optional
from pathlib import Path

import pandas as pd
from loguru import logger

from ..models.soil import SoilProfile, SoilLayer, SoilTexture
from ..models.location import Location
from ..models.crop import CropCharacteristics, CropType


class SoilService:
    """Service for soil analysis and crop-soil compatibility."""

    # Texture properties for plant available water
    TEXTURE_PROPERTIES = {
        SoilTexture.SAND: {"awc": 0.08, "fc": 0.10, "wp": 0.04, "bd": 1.55},
        SoilTexture.LOAMY_SAND: {"awc": 0.12, "fc": 0.15, "wp": 0.06, "bd": 1.50},
        SoilTexture.SANDY_LOAM: {"awc": 0.16, "fc": 0.20, "wp": 0.09, "bd": 1.45},
        SoilTexture.LOAM: {"awc": 0.20, "fc": 0.28, "wp": 0.13, "bd": 1.40},
        SoilTexture.SILT_LOAM: {"awc": 0.22, "fc": 0.30, "wp": 0.14, "bd": 1.35},
        SoilTexture.SILT: {"awc": 0.20, "fc": 0.28, "wp": 0.12, "bd": 1.30},
        SoilTexture.SANDY_CLAY_LOAM: {"awc": 0.18, "fc": 0.26, "wp": 0.14, "bd": 1.40},
        SoilTexture.CLAY_LOAM: {"awc": 0.20, "fc": 0.32, "wp": 0.18, "bd": 1.35},
        SoilTexture.SILTY_CLAY_LOAM: {"awc": 0.20, "fc": 0.34, "wp": 0.19, "bd": 1.30},
        SoilTexture.SANDY_CLAY: {"awc": 0.15, "fc": 0.28, "wp": 0.17, "bd": 1.35},
        SoilTexture.SILTY_CLAY: {"awc": 0.16, "fc": 0.36, "wp": 0.20, "bd": 1.30},
        SoilTexture.CLAY: {"awc": 0.16, "fc": 0.38, "wp": 0.22, "bd": 1.25},
    }

    # pH suitability ranges for crop types
    PH_SUITABILITY = {
        CropType.CEREAL: (5.5, 7.5),
        CropType.LEGUME: (6.0, 7.5),
        CropType.OILSEED: (5.5, 7.5),
        CropType.ROOT_TUBER: (5.0, 7.0),
        CropType.VEGETABLE: (5.5, 7.0),
        CropType.FORAGE: (5.5, 7.5),
        CropType.FIBER: (5.5, 7.5),
        CropType.COVER_CROP: (5.0, 8.0),
    }

    def __init__(self):
        pass

    def analyze_profile(self, profile: SoilProfile) -> Dict:
        """Comprehensive soil profile analysis."""
        return {
            "location_id": profile.location_id,
            "max_depth_cm": profile.max_depth,
            "num_layers": len(profile.layers),
            "total_soc_t_ha": profile.total_organic_carbon,
            "average_ph": profile.average_ph,
            "drainage_class": profile.drainage_class,
            "taxonomic_class": profile.taxonomic_class,
            "layer_details": [self._analyze_layer(layer) for layer in profile.layers],
            "plant_available_water_mm": self.calculate_paw(profile),
            "nutrient_status": self.assess_nutrients(profile),
            "constraints": self.identify_constraints(profile),
        }

    def _analyze_layer(self, layer: SoilLayer) -> Dict:
        props = self.TEXTURE_PROPERTIES.get(layer.texture, {})
        return {
            "depth_range": f"{layer.depth_top}-{layer.depth_bottom} cm",
            "thickness_cm": layer.thickness,
            "texture": layer.texture.value,
            "organic_carbon_pct": layer.organic_carbon,
            "ph": layer.ph,
            "bulk_density": layer.bulk_density or props.get("bd"),
            "awc_estimate": props.get("awc"),
            "field_capacity": props.get("fc"),
            "wilting_point": props.get("wp"),
            "nitrogen_pct": layer.nitrogen,
            "phosphorus_mg_kg": layer.phosphorus,
            "potassium_mg_kg": layer.potassium,
            "cec": layer.cec,
        }

    def calculate_paw(self, profile: SoilProfile, root_depth_cm: float = 100) -> float:
        """Calculate plant available water in mm to root depth."""
        total_paw_mm = 0.0

        for layer in profile.layers:
            if layer.depth_top >= root_depth_cm:
                break

            layer_root_depth = min(layer.depth_bottom, root_depth_cm) - layer.depth_top
            if layer_root_depth <= 0:
                continue

            # Use layer AWC or texture estimate
            awc = layer.available_water_capacity
            if awc is None:
                props = self.TEXTURE_PROPERTIES.get(layer.texture, {})
                awc = props.get("awc", 0.15)

            # Convert to mm (AWC fraction * depth_cm * 10)
            total_paw_mm += awc * layer_root_depth * 10

        return round(total_paw_mm, 1)

    def assess_nutrients(self, profile: SoilProfile) -> Dict:
        """Assess soil nutrient status."""
        status = {"nitrogen": "unknown", "phosphorus": "unknown", "potassium": "unknown"}

        for layer in profile.layers[:3]:  # Top 3 layers
            if layer.nitrogen is not None:
                if layer.nitrogen > 0.2:
                    status["nitrogen"] = "high"
                elif layer.nitrogen > 0.1:
                    status["nitrogen"] = "medium"
                else:
                    status["nitrogen"] = "low"

            if layer.phosphorus is not None:
                if layer.phosphorus > 30:
                    status["phosphorus"] = "high"
                elif layer.phosphorus > 15:
                    status["phosphorus"] = "medium"
                else:
                    status["phosphorus"] = "low"

            if layer.potassium is not None:
                if layer.potassium > 200:
                    status["potassium"] = "high"
                elif layer.potassium > 100:
                    status["potassium"] = "medium"
                else:
                    status["potassium"] = "low"

        return status

    def identify_constraints(self, profile: SoilProfile) -> List[str]:
        """Identify soil constraints for crop production."""
        constraints = []

        # pH constraints
        avg_ph = profile.average_ph
        if avg_ph is not None:
            if avg_ph < 5.0:
                constraints.append("Strongly acidic - liming required")
            elif avg_ph < 5.5:
                constraints.append("Moderately acidic - may limit legumes")
            elif avg_ph > 8.0:
                constraints.append("Strongly alkaline - micronutrient issues")
            elif avg_ph > 7.5:
                constraints.append("Moderately alkaline")

        # Organic carbon
        if profile.total_organic_carbon < 20:  # t/ha
            constraints.append("Low soil organic carbon - needs organic matter")

        # Salinity/sodicity (if EC/ESP data available)
        # Would need additional data

        # Drainage
        if profile.drainage_class:
            poor_classes = ["poorly", "very poorly", "somewhat poorly"]
            if any(pc in profile.drainage_class.lower() for pc in poor_classes):
                constraints.append(f"Drainage limitation: {profile.drainage_class}")

        # Compaction (high bulk density)
        for layer in profile.layers:
            if layer.bulk_density and layer.bulk_density > 1.6:
                constraints.append(f"Potential compaction at {layer.depth_top}-{layer.depth_bottom} cm")
                break

        return constraints

    def crop_suitability(
        self,
        profile: SoilProfile,
        crop: CropCharacteristics,
    ) -> Dict:
        """Evaluate crop suitability for soil profile."""
        score = 100
        factors = []

        # pH suitability
        ph_range = self.PH_SUITABILITY.get(crop.crop_type, (5.0, 8.0))
        avg_ph = profile.average_ph

        if avg_ph is not None:
            if avg_ph < ph_range[0]:
                penalty = (ph_range[0] - avg_ph) * 15
                score -= penalty
                factors.append(f"pH {avg_ph:.1f} below optimal {ph_range[0]} (-{penalty:.0f})")
            elif avg_ph > ph_range[1]:
                penalty = (avg_ph - ph_range[1]) * 10
                score -= penalty
                factors.append(f"pH {avg_ph:.1f} above optimal {ph_range[1]} (-{penalty:.0f})")
            else:
                factors.append(f"pH {avg_ph:.1f} within optimal range {ph_range}")

        # Root depth vs soil depth
        if profile.max_depth < crop.root_depth_cm:
            penalty = 20
            score -= penalty
            factors.append(f"Soil depth {profile.max_depth}cm < root depth {crop.root_depth_cm}cm (-{penalty})")

        # Drainage vs crop needs
        if profile.drainage_class and crop.crop_type in [CropType.LEGUME, CropType.ROOT_TUBER]:
            if "poorly" in profile.drainage_class.lower():
                penalty = 15
                score -= penalty
                factors.append(f"Poor drainage unsuitable for {crop.crop_type.value} (-{penalty})")

        # SOC level
        if profile.total_organic_carbon < 15:
            penalty = 10
            score -= penalty
            factors.append(f"Low SOC ({profile.total_organic_carbon} t/ha) (-{penalty})")

        score = max(0, min(100, score))

        return {
            "crop": crop.name,
            "suitability_score": round(score),
            "rating": self._score_to_rating(score),
            "factors": factors,
            "recommendations": self._get_recommendations(profile, crop, factors),
        }

    def _score_to_rating(self, score: float) -> str:
        if score >= 80:
            return "Highly Suitable"
        elif score >= 60:
            return "Moderately Suitable"
        elif score >= 40:
            return "Marginally Suitable"
        else:
            return "Not Suitable"

    def _get_recommendations(self, profile: SoilProfile, crop: CropCharacteristics, factors: List[str]) -> List[str]:
        recs = []

        if profile.average_ph and profile.average_ph < 5.5:
            recs.append("Apply agricultural lime to raise pH")

        if profile.total_organic_carbon < 20:
            recs.append("Incorporate organic matter (compost, manure, cover crops)")

        if profile.drainage_class and "poorly" in profile.drainage_class.lower():
            recs.append("Consider drainage improvement or raised beds")

        if crop.crop_type == CropType.LEGUME and profile.average_ph and profile.average_ph < 6.0:
            recs.append("Ensure pH > 6.0 for effective rhizobium nodulation")

        return recs

    def create_profile_from_survey(
        self,
        location_id: str,
        survey_data: Dict,
    ) -> SoilProfile:
        """Create SoilProfile from survey/grid data."""
        layers = []
        for layer_data in survey_data.get("layers", []):
            layer = SoilLayer(
                depth_top=layer_data["depth_top"],
                depth_bottom=layer_data["depth_bottom"],
                texture=SoilTexture(layer_data["texture"]),
                organic_carbon=layer_data.get("organic_carbon"),
                ph=layer_data.get("ph"),
                bulk_density=layer_data.get("bulk_density"),
                nitrogen=layer_data.get("nitrogen"),
                phosphorus=layer_data.get("phosphorus"),
                potassium=layer_data.get("potassium"),
                cec=layer_data.get("cec"),
                available_water_capacity=layer_data.get("awc"),
            )
            layers.append(layer)

        return SoilProfile(
            location_id=location_id,
            layers=layers,
            drainage_class=survey_data.get("drainage_class"),
            taxonomic_class=survey_data.get("taxonomic_class"),
            source=survey_data.get("source", "survey"),
        )