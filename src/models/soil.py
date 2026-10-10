"""Soil profile and layer models."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


class SoilTexture(str, Enum):
    """USDA soil texture classes."""
    SAND = "sand"
    LOAMY_SAND = "loamy_sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    SILT = "silt"
    SANDY_CLAY_LOAM = "sandy_clay_loam"
    CLAY_LOAM = "clay_loam"
    SILTY_CLAY_LOAM = "silty_clay_loam"
    SANDY_CLAY = "sandy_clay"
    SILTY_CLAY = "silty_clay"
    CLAY = "clay"


class SoilLayer(BaseModel):
    """A single soil horizon/layer."""
    depth_top: float = Field(..., ge=0, description="Top depth in cm")
    depth_bottom: float = Field(..., ge=0, description="Bottom depth in cm")
    texture: SoilTexture = Field(..., description="USDA texture class")
    organic_carbon: Optional[float] = Field(None, ge=0, le=100, description="Organic carbon %")
    ph: Optional[float] = Field(None, ge=3, le=10, description="pH in water")
    bulk_density: Optional[float] = Field(None, ge=0.5, le=2.0, description="Bulk density g/cm³")
    nitrogen: Optional[float] = Field(None, ge=0, description="Total nitrogen %")
    phosphorus: Optional[float] = Field(None, ge=0, description="Available phosphorus mg/kg")
    potassium: Optional[float] = Field(None, ge=0, description="Exchangeable potassium mg/kg")
    cec: Optional[float] = Field(None, ge=0, description="Cation exchange capacity cmol+/kg")
    available_water_capacity: Optional[float] = Field(None, ge=0, le=1, description="AWC fraction")

    @property
    def thickness(self) -> float:
        return self.depth_bottom - self.depth_top

    @field_validator("depth_bottom")
    @classmethod
    def validate_depth(cls, v, info):
        if info.data.get("depth_top") is not None and v <= info.data["depth_top"]:
            raise ValueError("depth_bottom must be greater than depth_top")
        return v


class SoilProfile(BaseModel):
    """Complete soil profile with multiple layers."""
    location_id: str = Field(..., description="Reference to location")
    layers: List[SoilLayer] = Field(..., min_length=1, description="Soil layers from surface down")
    drainage_class: Optional[str] = Field(None, description="NRCS drainage class")
    taxonomic_class: Optional[str] = Field(None, description="USDA soil taxonomy")
    source: str = Field(default="survey", description="Data source: survey, grids, or model")

    @property
    def max_depth(self) -> float:
        return max(layer.depth_bottom for layer in self.layers)

    @property
    def total_organic_carbon(self) -> float:
        """Total organic carbon stock in t/ha to max depth."""
        total = 0.0
        for layer in self.layers:
            if layer.organic_carbon and layer.bulk_density:
            
                total += layer.organic_carbon * layer.bulk_density * layer.thickness * 10
        return round(total, 2)

    @property
    def average_ph(self) -> Optional[float]:
        """Depth-weighted average pH."""
        weighted_sum = 0.0
        total_thickness = 0.0
        for layer in self.layers:
            if layer.ph:
                weighted_sum += layer.ph * layer.thickness
                total_thickness += layer.thickness
        return round(weighted_sum / total_thickness, 2) if total_thickness > 0 else None

    def get_layer_at_depth(self, depth_cm: float) -> Optional[SoilLayer]:
        """Find the layer containing a specific depth."""
        for layer in self.layers:
            if layer.depth_top <= depth_cm < layer.depth_bottom:
                return layer
        return None