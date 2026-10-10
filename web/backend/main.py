"""
Crop Shift - Farm Future Simulator
Web backend using FastAPI
"""
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from loguru import logger

# Import our existing services (src is a package, so use src.* prefix
# to keep relative imports like ..api.power working inside services)
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env from project root so NASA_API_KEY and base URLs are available
load_dotenv(PROJECT_ROOT / ".env")
NASA_API_KEY = os.getenv("NASA_API_KEY")
POWER_BASE_URL = os.getenv("NASA_POWER_BASE_URL", "").rstrip("/") or None

logger.remove()
logger.add(sys.stderr, level=os.getenv("LOG_LEVEL", "INFO").upper())

if not NASA_API_KEY:
    # POWER is public and works without a key; the key only raises rate limits.
    logger.warning("NASA_API_KEY not set - using NASA's anonymous rate limits")

from src.models.location import Location
from src.models.soil import SoilProfile, SoilLayer, SoilTexture
from src.models.crop import Crop, CropCharacteristics, CropRotation, CropType
from src.models.climate import ClimateSummary
from src.models.recommendation import Priority, RotationComparison
from src.services.crop_service import CropService
from src.services.soil_service import SoilService
from src.services.climate_service import ClimateService
from src.services.rotation_service import RotationService
from src.services.recommendation_service import RecommendationService
from src.api.power import POWERClient
from src.api.modis import MODISClient


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    if _climate_service is not None:
        await _climate_service.close()


# Initialize FastAPI app
app = FastAPI(
    title="Crop Shift - Farm Future Simulator",
    description="NASA-powered crop rotation decision support with climate scenario testing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent
STATIC_DIR = WEB_DIR / "static"

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global service instances
crop_service = CropService()
soil_service = SoilService()
rotation_service = RotationService(soil_service=soil_service)
recommendation_service = RecommendationService(
    rotation_service=rotation_service,
    crop_service=crop_service,
    soil_service=soil_service,
)

# NASA API clients (lazy initialization)
_power_client = None
_modis_client = None
_climate_service = None


def get_climate_service() -> ClimateService:
    global _power_client, _modis_client, _climate_service
    if _climate_service is None:
        _power_client = POWERClient(api_key=NASA_API_KEY, base_url=POWER_BASE_URL)
        _modis_client = MODISClient()
        _climate_service = ClimateService(power_client=_power_client, modis_client=_modis_client)

    return _climate_service


# Request/Response Models
class FarmInput(BaseModel):
    """Farmer's field input"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    farm_name: Optional[str] = "My Farm"
    soil_texture: str = Field(default="loam", description="Topsoil texture")
    soil_ph: float = Field(default=6.5, ge=4.0, le=9.0)
    soil_organic_carbon: float = Field(default=2.0, ge=0, le=10, description="% organic carbon")
    water_source: str = Field(default="rainfed", description="rainfed, irrigation, mixed")
    crop_history: List[str] = Field(default_factory=list, description="Previous crops grown")
    priorities: Dict[str, float] = Field(
        default_factory=lambda: {
            "yield": 0.3,
            "soil_health": 0.25,
            "water_conservation": 0.2,
            "risk_reduction": 0.15,
            "profitability": 0.1
        }
    )


class ClimateScenario(BaseModel):
    """Climate modification scenario for 'What If' simulation"""
    temperature_change_c: float = Field(default=0, ge=-5, le=5, description="Temperature change in °C")
    precipitation_change_pct: float = Field(default=0, ge=-50, le=50, description="Precipitation change %")
    co2_ppm: Optional[float] = Field(default=None, description="CO2 concentration ppm")
    scenario_name: str = Field(default="Custom Scenario")


class SimulationRequest(BaseModel):
    """Full simulation request"""
    farm: FarmInput
    scenario: Optional[ClimateScenario] = None
    rotation_years: int = Field(default=3, ge=2, le=5)
    max_recommendations: int = Field(default=5, ge=1, le=10)


class CropRecommendation(BaseModel):
    """Simplified crop recommendation for frontend"""
    name: str
    crop_type: str
    water_need_mm: float
    drought_tolerance: int
    n_fixation: float
    soil_health_impact: int
    market_value: Optional[float]
    growing_days: int


class RotationResult(BaseModel):
    """Rotation evaluation result"""
    name: str
    crops: List[str]
    overall_score: float
    priority_scores: Dict[str, float]
    soil_health_score: float
    water_score: float
    economic_score: float
    climate_resilience_score: float
    details: Dict[str, Any]


class SimulationResponse(BaseModel):
    """Complete simulation response"""
    farm_name: str
    location: Dict[str, float]
    baseline_climate: Dict[str, Any]
    scenario_climate: Optional[Dict[str, Any]] = None
    recommendations: List[RotationResult]
    best_rotation: Optional[RotationResult]
    insights: List[str]
    warnings: List[str]
    data_source: Dict[str, Any] = Field(
        default_factory=dict,
        description="Which NASA sources contributed and over what period",
    )


def create_soil_profile(farm: FarmInput) -> SoilProfile:
    """Create soil profile from farm input"""
    texture_map = {
        "sand": SoilTexture.SAND,
        "loamy_sand": SoilTexture.LOAMY_SAND,
        "sandy_loam": SoilTexture.SANDY_LOAM,
        "loam": SoilTexture.LOAM,
        "silt_loam": SoilTexture.SILT_LOAM,
        "silt": SoilTexture.SILT,
        "clay_loam": SoilTexture.CLAY_LOAM,
        "clay": SoilTexture.CLAY,
    }

    texture = texture_map.get(farm.soil_texture.lower(), SoilTexture.LOAM)

    layers = [
        SoilLayer(
            depth_top=0,
            depth_bottom=20,
            texture=texture,
            organic_carbon=farm.soil_organic_carbon,
            ph=farm.soil_ph,
            bulk_density=1.35,
            nitrogen=farm.soil_organic_carbon * 0.06,
            phosphorus=25,
            potassium=180,
            cec=20,
            available_water_capacity=0.20,
        ),
        SoilLayer(
            depth_top=20,
            depth_bottom=50,
            texture=texture,
            organic_carbon=farm.soil_organic_carbon * 0.5,
            ph=farm.soil_ph + 0.2,
            bulk_density=1.45,
            nitrogen=farm.soil_organic_carbon * 0.03,
            phosphorus=15,
            potassium=150,
            cec=22,
            available_water_capacity=0.18,
        ),
        SoilLayer(
            depth_top=50,
            depth_bottom=100,
            texture=texture,
            organic_carbon=farm.soil_organic_carbon * 0.2,
            ph=farm.soil_ph + 0.4,
            bulk_density=1.55,
            nitrogen=0.02,
            phosphorus=10,
            potassium=120,
            cec=25,
            available_water_capacity=0.16,
        ),
    ]

    return SoilProfile(
        location_id=f"{farm.latitude},{farm.longitude}",
        layers=layers,
        drainage_class="well_drained" if farm.water_source != "flooded" else "poorly_drained",
        source="farmer_input",
    )


def apply_climate_scenario(
    baseline: ClimateSummary,
    scenario: ClimateScenario,
) -> ClimateSummary:
    """Apply climate scenario modifications to baseline"""
    modified = ClimateSummary(
        location_id=baseline.location_id,
        start_date=baseline.start_date,
        end_date=baseline.end_date,
        mean_temp=(baseline.mean_temp or 0) + scenario.temperature_change_c,
        max_temp=(baseline.max_temp or 0) + scenario.temperature_change_c,
        min_temp=(baseline.min_temp or 0) + scenario.temperature_change_c,
        total_precipitation=(baseline.total_precipitation or 0) * (1 + scenario.precipitation_change_pct / 100),
        total_pet=(baseline.total_pet or 0) * (1 + scenario.temperature_change_c * 0.05),
        mean_humidity=baseline.mean_humidity,
        aridity_index=None,
        growing_degree_days=baseline.growing_degree_days,
        frost_days=max(0, (baseline.frost_days or 0) - int(scenario.temperature_change_c * 5)),
        heat_stress_days=(baseline.heat_stress_days or 0) + max(0, int(scenario.temperature_change_c * 10)),
    )

    # Recalculate aridity index
    if modified.total_pet and modified.total_precipitation and modified.total_precipitation > 0:
        modified.aridity_index = modified.total_pet / modified.total_precipitation

    return modified


def format_recommendation(rec) -> RotationResult:
    """Format recommendation for frontend"""

    def scaled(value, divisor, base=50.0):
        """Map an unbounded metric onto a 0-100 display scale."""
        if value is None:
            return None
        return round(min(100.0, max(0.0, value / divisor * base)), 1)

    return RotationResult(
        name=rec.rotation.name,
        crops=[c.characteristics.name for c in rec.rotation.crops],
        overall_score=rec.overall_score,
        priority_scores={ps.priority.value: ps.score for ps in rec.priority_scores},
        soil_health_score=scaled(
            rec.soil_health_assessment.get("average_soil_health_index"), 2.5, 100
        ),
        water_score=scaled(rec.water_assessment.get("avg_drought_tolerance"), 5, 100),
        economic_score=scaled(rec.economic_assessment.get("avg_annual_profit_usd_ha"), 1000, 100),
        climate_resilience_score=scaled(
            rec.climate_resilience_assessment.get("avg_drought_tolerance"), 5, 100
        ),
        details={
            "soil_health": rec.soil_health_assessment,
            "water": rec.water_assessment,
            "economic": rec.economic_assessment,
            "climate": rec.climate_resilience_assessment,
            "risks": rec.risk_assessment,
        }
    )


def generate_insights(
    recommendations: List[RotationResult],
    baseline: ClimateSummary,
    scenario: Optional[ClimateScenario],
) -> List[str]:
    """Generate actionable insights"""
    insights = []

    if not recommendations:
        return []

    best = recommendations[0]

    # Climate insights
    if baseline.aridity_index and baseline.aridity_index > 1.5:
        insights.append(
            f"⚠️ Your area is arid (aridity index: {baseline.aridity_index:.1f}). "
            f"Prioritize drought-tolerant crops and water conservation."
        )

    if baseline.heat_stress_days and baseline.heat_stress_days > 10:
        insights.append(
            f"🌡️ {baseline.heat_stress_days} days/year exceed 35°C. "
            f"Heat-tolerant varieties recommended."
        )

    # Scenario insights
    if scenario:
        if scenario.temperature_change_c > 0:
            insights.append(
                f"🔥 With +{scenario.temperature_change_c}°C warming, "
                f"heat stress days increase to ~{baseline.heat_stress_days + int(scenario.temperature_change_c * 10)}/year."
            )
        if scenario.precipitation_change_pct < 0:
            insights.append(
                f"💧 {abs(scenario.precipitation_change_pct)}% less rainfall means "
                f"~{abs(scenario.precipitation_change_pct) * (baseline.total_precipitation or 800) / 100:.0f}mm less water annually."
            )

    # Rotation insights
    if best.crops:
        crop_names = " → ".join(best.crops)
        insights.append(
            f"✅ Best rotation: **{crop_names}** (Score: {best.overall_score:.0f}/100)"
        )

    if best.priority_scores.get("soil_health", 0) > 70:
        insights.append("🌱 This rotation builds soil organic carbon and structure over time.")

    if best.priority_scores.get("water_conservation", 0) > 70:
        insights.append("💧 High water efficiency - suitable for water-limited conditions.")

    # Water balance across the whole rotation
    water = best.details.get("water", {})
    annual_need = water.get("avg_annual_need_mm")
    if annual_need and baseline.total_precipitation:
        rain = baseline.total_precipitation
        ratio = annual_need / rain
        if ratio > 1.0:
            insights.append(
                f"💧 This rotation needs about {annual_need:.0f}mm/yr of water but your "
                f"area receives {rain:.0f}mm. Budget for {ratio:.1f}× the rainfall."
            )
        elif ratio > 0.8:
            insights.append(
                f"💧 Water use ({annual_need:.0f}mm/yr) roughly matches your rainfall "
                f"({rain:.0f}mm/yr). Keep irrigation ready for dry spells."
            )
        else:
            insights.append(
                f"💧 Rainfall ({rain:.0f}mm/yr) covers this rotation's {annual_need:.0f}mm "
                f"of water need. Rainfed farming is viable here."
            )

    # Nitrogen balance
    n_balance = best.details.get("soil_health", {}).get("total_n_balance_kg_ha")
    if n_balance is not None:
        if n_balance > 0:
            insights.append(f"🌿 Net nitrogen gain: +{n_balance:.0f} kg/ha/yr from legumes.")
        elif n_balance < -50:
            insights.append(f"⚠️ Nitrogen deficit: {n_balance:.0f} kg/ha/yr. Plan for fertilizer.")

    return insights


def generate_warnings(
    recommendations: List[RotationResult],
    baseline: ClimateSummary,
    scenario: Optional[ClimateScenario],
    farm: FarmInput,
) -> List[str]:
    """Generate risk warnings"""
    warnings = []

    if farm.soil_ph < 5.5:
        warnings.append(f"⚠️ Soil pH ({farm.soil_ph}) is acidic. Liming recommended for legumes.")

    if farm.soil_ph > 7.8:
        warnings.append(f"⚠️ Soil pH ({farm.soil_ph}) is alkaline. Micronutrient deficiencies likely.")

    if farm.soil_organic_carbon < 1.0:
        warnings.append("⚠️ Very low organic carbon (<1%). Add compost/manure/cover crops.")

    if baseline.total_precipitation and baseline.total_precipitation < 400:
        warnings.append("⚠️ Low rainfall area. Irrigation or drought-tolerant crops essential.")

    if baseline.frost_days and baseline.frost_days > 60:
        warnings.append(
            f"⚠️ {baseline.frost_days} frost days/yr. Sowing dates need to avoid "
            f"frost risk, or use greenhouse cover."
        )

    # Gating temperature for the warm-season crops in these rotations
    if baseline.mean_temp is not None and baseline.mean_temp < 12:
        warnings.append(
            f"⚠️ Mean temperature is only {baseline.mean_temp:.1f}°C. Cool-season "
            f"crops and shorter rotations will outperform warm-season plans."
        )

    if scenario and scenario.temperature_change_c > 2:
        warnings.append("🚨 +2°C+ warming may exceed crop thermal limits. Consider heat-tolerant varieties.")

    if scenario and scenario.precipitation_change_pct < -30:
        warnings.append("🚨 >30% rainfall reduction. Major irrigation investment needed.")

    if not warnings:
        warnings.append("✅ No major risks found for these conditions.")

    return warnings


# API Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def health_check():
    """Liveness plus a real probe of the NASA POWER endpoint."""
    power_ok = False
    power_error = None
    try:
        service = get_climate_service()
        location = Location(latitude=23.8103, longitude=90.4125)
        recent = await service.power.fetch_climate_data(
            location,
            f"{datetime.now().year - 1}-01-01",
            f"{datetime.now().year - 1}-01-03",
        )
        power_ok = bool(recent) and recent[0].temperature_2m_mean is not None
    except Exception as e:
        power_error = str(e)
        logger.warning(f"NASA POWER health probe failed: {e}")

    return {
        "status": "ok" if power_ok else "degraded",
        "service": "Crop Shift - Farm Future Simulator",
        "nasa_power": {
            "reachable": power_ok,
            "community": "AG (agroclimatology)",
            "error": power_error,
        },
    }


@app.get("/api/crops")
async def list_crops(crop_type: Optional[str] = None):
    """List available crops"""
    crops = crop_service.list_crops(
        CropType(crop_type) if crop_type else None
    )
    return {
        "crops": [
            {
                "name": c.name,
                "type": c.crop_type.value,
                "water_need_mm": c.water_requirement_mm,
                "drought_tolerance": c.drought_tolerance,
                "n_fixation_kg_ha": c.n_fixation_kg_ha,
                "soil_health_index": c.soil_health_index,
                "market_value_usd_ton": c.market_value_usd_ton,
                "growing_degree_days": c.growing_degree_days,
                "root_depth_cm": c.root_depth_cm,
            }
            for c in crops
        ]
    }


@app.get("/api/crop-types")
async def list_crop_types():
    return {"types": [ct.value for ct in CropType]}


@app.post("/api/simulate", response_model=SimulationResponse)
async def run_simulation(request: SimulationRequest):
    """
    Run the Farm Future Simulation with optional climate scenario
    """
    farm = request.farm
    location = Location(latitude=farm.latitude, longitude=farm.longitude)

    logger.info(f"Simulating for {farm.farm_name} at {location}")

    try:
        # Baseline climate: mean of the most recent complete POWER years
        climate_service = get_climate_service()

        summaries = await climate_service.fetch_recent_annual_summaries(location, years=5)
        start_year = min(s.start_date.year for s in summaries)
        end_year = max(s.start_date.year for s in summaries)

        def avg(attr, default=0.0):
            """Mean of a summary field, skipping years where it is missing."""
            vals = [getattr(s, attr) for s in summaries if getattr(s, attr) is not None]
            return sum(vals) / len(vals) if vals else default

        baseline_climate = ClimateSummary(
            location_id=f"{location.latitude},{location.longitude}",
            start_date=date(start_year, 1, 1),
            end_date=date(end_year, 12, 31),
            mean_temp=round(avg("mean_temp"), 2),
            max_temp=round(avg("max_temp"), 2),
            min_temp=round(avg("min_temp"), 2),
            total_precipitation=round(avg("total_precipitation"), 1),
            total_pet=round(avg("total_pet"), 1),
            mean_humidity=round(avg("mean_humidity"), 1),
            aridity_index=round(avg("aridity_index"), 2),
            growing_degree_days=int(avg("growing_degree_days")),
            frost_days=int(avg("frost_days")),
            heat_stress_days=int(avg("heat_stress_days")),
        )

        # Apply scenario if provided
        scenario_climate = None
        if request.scenario and (request.scenario.temperature_change_c != 0 or request.scenario.precipitation_change_pct != 0):
            scenario_climate = apply_climate_scenario(baseline_climate, request.scenario)
            evaluation_climate = scenario_climate
        else:
            evaluation_climate = baseline_climate

        # Create soil profile
        soil_profile = create_soil_profile(farm)

        # Parse priorities
        priorities = []
        for p, weight in farm.priorities.items():
            if weight > 0:
                try:
                    priorities.append(Priority(p))
                except ValueError:
                    pass

        if not priorities:
            priorities = [Priority.YIELD, Priority.SOIL_HEALTH, Priority.WATER_CONSERVATION]

        # Generate recommendations
        comparison = recommendation_service.generate_recommendations(
            location=location,
            soil_profile=soil_profile,
            climate_summary=evaluation_climate,
            priorities=priorities,
            years=request.rotation_years,
            max_recommendations=request.max_recommendations,
        )

        # Format results
        recommendations = [format_recommendation(r) for r in comparison.recommendations]
        best = recommendations[0] if recommendations else None

        if best is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No crop rotation fits these soil and climate conditions. "
                    "Try loosening the soil constraints or lowering the heat "
                    "stress, then run the simulation again."
                ),
            )

        insights = generate_insights(recommendations, baseline_climate, request.scenario)
        warnings = generate_warnings(recommendations, baseline_climate, request.scenario, farm)

        return SimulationResponse(
            farm_name=farm.farm_name,
            location={"latitude": farm.latitude, "longitude": farm.longitude},
            baseline_climate=baseline_climate.model_dump(),
            scenario_climate=scenario_climate.model_dump() if scenario_climate else None,
            recommendations=recommendations,
            best_rotation=best,
            insights=insights,
            warnings=warnings,
            data_source={
                "provider": "NASA POWER",
                "product": "POWER Daily Point - Agroclimatology (AG)",
                "variables": ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "GWETTOP"],
                "et0_method": "Hargreaves (FAO-56) estimated from daily temperature range",
                "period": f"{start_year}-{end_year}",
                "years_with_data": len(summaries),
                "years_requested": end_year - start_year + 1,
"endpoint": POWER_BASE_URL or POWERClient.BASE_URL,
                "community": "AG",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simulation error: {e}")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}") from e


@app.post("/api/quick-simulate")
async def quick_simulate(
    latitude: float = Body(...),
    longitude: float = Body(...),
    temp_change: float = Body(0),
    precip_change: float = Body(0),
):
    """Quick simulation endpoint for the 'What If' toggle"""
    farm = FarmInput(latitude=latitude, longitude=longitude)
    scenario = ClimateScenario(
        temperature_change_c=temp_change,
        precipitation_change_pct=precip_change,
    ) if temp_change != 0 or precip_change != 0 else None

    request = SimulationRequest(farm=farm, scenario=scenario)
    return await run_simulation(request)


@app.get("/api/climate/{lat}/{lon}")
async def get_climate(lat: float, lon: float, years: int = 5):
    """Get historical climate data for a location"""
    location = Location(latitude=lat, longitude=lon)
    climate_service = get_climate_service()

    summaries = await climate_service.fetch_recent_annual_summaries(location, years=years)

    start_year = min(s.start_date.year for s in summaries)
    current_year = max(s.start_date.year for s in summaries)

    return {
        "location": {"lat": lat, "lon": lon},
        "period": f"{start_year}-{current_year}",
        "annual_summaries": [s.model_dump() for s in summaries],
        "averages": {
            "mean_temp": sum(s.mean_temp or 0 for s in summaries) / len(summaries) if summaries else 0,
            "total_precipitation": sum(s.total_precipitation or 0 for s in summaries) / len(summaries) if summaries else 0,
            "aridity_index": sum(s.aridity_index or 0 for s in summaries) / len(summaries) if summaries and any(s.aridity_index for s in summaries) else 0,
        }
    }


if __name__ == "__main__":
    import uvicorn
    print("Starting Crop Shift on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)