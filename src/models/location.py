"""Location and geographic models."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class Location(BaseModel):
    """Geographic location with coordinate validation."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    elevation: Optional[float] = Field(None, ge=0, le=9000, description="Elevation in meters")
    name: Optional[str] = Field(None, description="Location name or identifier")
    timezone: Optional[str] = Field(None, description="IANA timezone identifier")

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def parse_coordinate(cls, v):
        if isinstance(v, str):
            return float(v)
        return v

    def to_tuple(self) -> tuple[float, float]:
        """Return as (lat, lon) tuple."""
        return (self.latitude, self.longitude)

    def __str__(self) -> str:
        parts = [f"{self.latitude:.4f}, {self.longitude:.4f}"]
        if self.name:
            parts.insert(0, self.name)
        if self.elevation:
            parts.append(f"elev={self.elevation}m")
        return " ".join(parts)