"""Data models for the crop rotation decision support tool."""
from .location import Location
from .soil import SoilProfile, SoilLayer
from .crop import Crop, CropRotation, CropCharacteristics
from .climate import ClimateData, ClimateProjection
from .recommendation import RotationRecommendation, RecommendationScore, Priority, RotationComparison

__all__ = [
    "Location",
    "SoilProfile",
    "SoilLayer",
    "Crop",
    "CropRotation",
    "CropCharacteristics",
    "ClimateData",
    "ClimateProjection",
    "RotationRecommendation",
    "RecommendationScore",
    "Priority",
    "RotationComparison",
]