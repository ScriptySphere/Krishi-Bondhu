"""Crop and rotation models."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from enum import Enum
from datetime import date


class CropType(str, Enum):
    """Major crop categories."""
    CEREAL = "cereal"
    LEGUME = "legume"
    OILSEED = "oilseed"
    ROOT_TUBER = "root_tuber"
    VEGETABLE = "vegetable"
    FORAGE = "forage"
    FIBER = "fiber"
    COVER_CROP = "cover_crop"
    FALLOW = "fallow"


class GrowthHabit(str, Enum):
    """Crop growth habit."""
    ANNUAL = "annual"
    BIENNIAL = "biennial"
    PERENNIAL = "perennial"


class CropCharacteristics(BaseModel):
    """Agronomic characteristics of a crop."""
    name: str = Field(..., description="Common crop name")
    scientific_name: Optional[str] = None
    crop_type: CropType
    growth_habit: GrowthHabit = GrowthHabit.ANNUAL




    water_requirement_mm: float = Field(..., ge=0, description="Seasonal water need in mm")
    drought_tolerance: int = Field(..., ge=1, le=5, description="1=sensitive, 5=tolerant")
    irrigation_response: float = Field(default=1.0, ge=0, le=2, description="Yield response to irrigation")


    n_fixation_kg_ha: float = Field(default=0, ge=0, description="Nitrogen fixed per hectare")
    n_uptake_kg_ha: float = Field(..., ge=0, description="Nitrogen uptake per hectare")
    p_uptake_kg_ha: float = Field(..., ge=0, description="Phosphorus uptake per hectare")
    k_uptake_kg_ha: float = Field(..., ge=0, description="Potassium uptake per hectare")


    residue_cn_ratio: float = Field(..., gt=0, description="Residue C:N ratio")
    root_depth_cm: float = Field(..., ge=0, description="Effective rooting depth")
    biomass_kg_ha: float = Field(..., ge=0, description="Above-ground biomass")
    soil_health_index: float = Field(default=0, ge=-2, le=2, description="Effect on soil health (-2 to +2)")

  
    min_temp_c: float = Field(..., description="Minimum growing temperature")
    max_temp_c: float = Field(..., description="Maximum growing temperature")
    optimal_temp_c: float = Field(..., description="Optimal growing temperature")
    frost_tolerance_c: float = Field(default=0, description="Frost tolerance (negative = tolerant)")
    growing_degree_days: int = Field(..., ge=0, description="GDD base 10°C to maturity")

  
    pest_break_value: int = Field(default=0, ge=0, le=3, description="Breaks pest cycles for following crops")
    disease_susceptibility: Dict[str, int] = Field(default_factory=dict, description="Disease susceptibility 1-5")


    market_value_usd_ton: Optional[float] = Field(None, ge=0, description="Market price per ton")
    production_cost_usd_ha: Optional[float] = Field(None, ge=0, description="Production cost per hectare")

    @field_validator("max_temp_c")
    @classmethod
    def validate_temp_range(cls, v, info):
        if info.data.get("min_temp_c") is not None and v <= info.data["min_temp_c"]:
            raise ValueError("max_temp_c must be greater than min_temp_c")
        return v


class Crop(BaseModel):
    """A crop instance in a rotation."""
    characteristics: CropCharacteristics
    variety: Optional[str] = None
    planting_date: Optional[date] = None
    harvest_date: Optional[date] = None
    expected_yield_ton_ha: Optional[float] = Field(None, ge=0)
    actual_yield_ton_ha: Optional[float] = Field(None, ge=0)
    management_notes: str = ""

    @property
    def season_length_days(self) -> Optional[int]:
        if self.planting_date and self.harvest_date:
            return (self.harvest_date - self.planting_date).days
        return None

    @property
    def nitrogen_balance(self) -> float:
        """Net N contribution (fixation - uptake)."""
        return self.characteristics.n_fixation_kg_ha - self.characteristics.n_uptake_kg_ha


class CropRotation(BaseModel):
    """A sequence of crops over multiple years."""
    name: str
    crops: List[Crop] = Field(..., min_length=2)
    years: int = Field(..., ge=2, description="Number of years in rotation")
    location_id: str

    @property
    def crops_per_year(self) -> List[List[Crop]]:
        """Group crops by year (assuming sequential)."""
   
        return [[crop] for crop in self.crops]

    @property
    def total_nitrogen_balance(self) -> float:
        return sum(crop.nitrogen_balance for crop in self.crops)

    @property
    def average_soil_health_index(self) -> float:
        return sum(crop.characteristics.soil_health_index for crop in self.crops) / len(self.crops)

    @property
    def crop_types(self) -> List[CropType]:
        return [crop.characteristics.crop_type for crop in self.crops]

    @property
    def has_legume(self) -> bool:
        return CropType.LEGUME in self.crop_types

    @property
    def has_cover_crop(self) -> bool:
        return CropType.COVER_CROP in self.crop_types

    def diversity_index(self) -> float:
        """Shannon diversity index of crop types."""
        from collections import Counter
        import math
        counts = Counter(self.crop_types)
        total = len(self.crop_types)
        return -sum((c/total) * math.log(c/total) for c in counts.values())