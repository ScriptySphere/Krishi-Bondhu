"""Climate data and projection models."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date
from enum import Enum


class ClimateVariable(str, Enum):
    """NASA POWER climate variables."""
    TEMPERATURE_2M = "T2M"
    TEMPERATURE_2M_MAX = "T2M_MAX"
    TEMPERATURE_2M_MIN = "T2M_MIN"
    PRECIPITATION = "PRECTOTCORR"
    RELATIVE_HUMIDITY = "RH2M"
    WIND_SPEED_10M = "WS10M"
    WIND_SPEED_50M = "WS50M"
    SOLAR_RADIATION = "ALLSKY_SFC_SW_DWN"
    PAR = "ALLSKY_SFC_PAR_TOT"
    SOIL_MOISTURE_0_10CM = "GWETTOP"
    SOIL_MOISTURE_10_40CM = "GWETROOT"
    SOIL_MOISTURE_40_100CM = "GWETPROF"
    EVAPOTRANSPIRATION = "EVAPOTRANSPIRATION"
    PET = "PET"


class ClimateData(BaseModel):
    """Daily climate data from NASA POWER."""
    location_id: str
    date: date
    temperature_2m_mean: Optional[float] = Field(None, description="°C")
    temperature_2m_max: Optional[float] = Field(None, description="°C")
    temperature_2m_min: Optional[float] = Field(None, description="°C")
    precipitation: Optional[float] = Field(None, ge=0, description="mm/day")
    relative_humidity: Optional[float] = Field(None, ge=0, le=100, description="%")
    wind_speed_10m: Optional[float] = Field(None, ge=0, description="m/s")
    solar_radiation: Optional[float] = Field(None, ge=0, description="MJ/m²/day")
    par: Optional[float] = Field(None, ge=0, description="MJ/m²/day")
    soil_moisture_surface: Optional[float] = Field(None, ge=0, le=1, description="0-10cm fraction")
    soil_moisture_root: Optional[float] = Field(None, ge=0, le=1, description="10-40cm fraction")
    soil_moisture_profile: Optional[float] = Field(None, ge=0, le=1, description="40-100cm fraction")
    evapotranspiration: Optional[float] = Field(None, ge=0, description="mm/day")
    pet: Optional[float] = Field(None, ge=0, description="mm/day")

    @property
    def vapor_pressure_deficit(self) -> Optional[float]:
        """Calculate VPD in kPa from T and RH."""
        if self.temperature_2m_mean is not None and self.relative_humidity is not None:




    
            es = 0.6108 * (17.27 * self.temperature_2m_mean / (self.temperature_2m_mean + 237.3)).exp()
            return round(es * (1 - self.relative_humidity / 100), 2)
        return None


class ClimateSummary(BaseModel):
    """Aggregated climate statistics for a growing season or year."""
    location_id: str
    start_date: date
    end_date: date
    mean_temp: Optional[float] = None
    max_temp: Optional[float] = None
    min_temp: Optional[float] = None
    total_precipitation: Optional[float] = None
    mean_humidity: Optional[float] = None
    total_et: Optional[float] = None
    total_pet: Optional[float] = None
    aridity_index: Optional[float] = Field(None, description="PET/P ratio")
    growing_degree_days: Optional[int] = Field(None, description="GDD base 10°C")
    frost_days: Optional[int] = None
    heat_stress_days: Optional[int] = Field(None, description="Days > 35°C")
    drought_index: Optional[float] = Field(None, description="Standardized precipitation index")


class ClimateProjection(BaseModel):
    """Future climate projection from CMIP6 or similar."""
    location_id: str
    scenario: str = Field(..., description="SSP scenario e.g. ssp245, ssp585")
    model: str = Field(..., description="Climate model name")
    period_start: int
    period_end: int
    temperature_change: Optional[float] = Field(None, description="°C change from baseline")
    precipitation_change_pct: Optional[float] = Field(None, description="% change from baseline")
    variables: Dict[str, float] = Field(default_factory=dict)

    @property
    def period_label(self) -> str:
        return f"{self.period_start}-{self.period_end}"