"""Climate analysis service using NASA data."""
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from ..api.power import POWERClient
from ..api.modis import MODISClient
from ..api.smap import SMAPClient, SMAPSoilMoistureService
from ..api.grace import GRACEClient, GRACEWaterStorageService
from ..models.location import Location
from ..models.climate import ClimateData, ClimateSummary, ClimateProjection, ClimateVariable
from ..models.crop import CropCharacteristics
from ..models.soil import SoilProfile


class ClimateService:
    """Service for climate data retrieval and analysis."""

    def __init__(
        self,
        power_client: Optional[POWERClient] = None,
        modis_client: Optional[MODISClient] = None,
        smap_client: Optional[SMAPClient] = None,
        grace_client: Optional[GRACEClient] = None,
    ):
        self.power = power_client or POWERClient()
        self.modis = modis_client or MODISClient()
        self.smap = smap_client or SMAPClient()
        self.smap_service = SMAPSoilMoistureService(self.smap)
        self.grace = grace_client or GRACEClient()
        self.grace_service = GRACEWaterStorageService(self.grace)

    async def fetch_comprehensive_climate(
        self,
        location: Location,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """Fetch climate data from all NASA sources."""
        logger.info(f"Fetching comprehensive climate data for {location}")

        results = {
            "location": {"lat": location.latitude, "lon": location.longitude},
            "period": f"{start_date} to {end_date}",
            "power": {},
            "modis": {},
            "smap": {},
            "grace": {},
        }



        try:
            power_data = await self.power.fetch_climate_data(location, start_date, end_date)
            results["power"] = {
                "daily_count": len(power_data),
                "summary": self._summarize_power(power_data),
            }
        except Exception as e:
            logger.error(f"POWER fetch failed: {e}")
            results["power"] = {"error": str(e)}



        try:
            modis_data = await self.modis.fetch_time_series(
                location, start_date, end_date, ["NDVI", "EVI", "LST_DAY", "LST_NIGHT"]
            )
            results["modis"] = modis_data
        except Exception as e:
            logger.error(f"MODIS fetch failed: {e}")
            results["modis"] = {"error": str(e)}



        try:
            smap_data = await self.smap.fetch_soil_moisture(location, start_date, end_date)
            results["smap"] = smap_data
        except Exception as e:
            logger.error(f"SMAP fetch failed: {e}")
            results["smap"] = {"error": str(e)}




        try:
            grace_data = await self.grace.fetch_tws(location, start_date, end_date)
            results["grace"] = grace_data
        except Exception as e:
            logger.error(f"GRACE fetch failed: {e}")
            results["grace"] = {"error": str(e)}

        return results

    def _summarize_power(self, daily_data: List[ClimateData]) -> Dict:
        """Create summary statistics from POWER daily data."""
        if not daily_data:
            return {}

        df = pd.DataFrame([d.model_dump() for d in daily_data])
        df = df.select_dtypes(include="number").replace(-999.0, float("nan")).astype(float)
        if df.empty:
            return {}

        summary = {}
        numeric_cols = df.columns

        for col in numeric_cols:
            vals = df[col].dropna()
            if len(vals) > 0:
                summary[col] = {
                    "mean": round(vals.mean(), 2),
                    "min": round(vals.min(), 2),
                    "max": round(vals.max(), 2),
                    "std": round(vals.std(), 2),
                    "count": len(vals),
                }




        if "precipitation" in df.columns:
            summary["total_precipitation_mm"] = round(df["precipitation"].dropna().sum(), 1)

        if "temperature_2m_mean" in df.columns:
            t_mean = df["temperature_2m_mean"].dropna()
            summary["growing_degree_days_base10"] = int((t_mean - 10).clip(lower=0).sum())

        if "pet" in df.columns and "precipitation" in df.columns:
            total_pet = df["pet"].dropna().sum()
            total_precip = df["precipitation"].dropna().sum()
            if total_precip > 0:
                summary["aridity_index"] = round(total_pet / total_precip, 2)

        return summary

    async def get_growing_season_climate(
        self,
        location: Location,
        crop: CropCharacteristics,
        planting_date: date,
        harvest_date: date,
    ) -> Dict:
        """Get climate summary for a specific crop growing season."""
        start = planting_date.isoformat()
        end = harvest_date.isoformat()

        power_data = await self.power.fetch_climate_data(location, start, end)
        summary = self._summarize_power(power_data)



        summary["crop_assessment"] = self._assess_crop_climate_fit(power_data, crop)



   
        smap_data = await self.smap_service.get_growing_season_moisture(
            location, planting_date, harvest_date, "rootzone"
        )
        summary["soil_moisture"] = smap_data

        return summary

    def _assess_crop_climate_fit(
        self,
        daily_data: List[ClimateData],
        crop: CropCharacteristics,
    ) -> Dict:
        """Assess how well climate matches crop requirements."""
        if not daily_data:
            return {"error": "No climate data"}

        df = pd.DataFrame([d.model_dump() for d in daily_data])
        df = df.select_dtypes(include="number").replace(-999.0, float("nan")).astype(float)
        if df.empty:
            return {"error": "No usable climate data for this location"}

        assessment = {
            "temperature_fit": "unknown",
            "water_fit": "unknown",
            "heat_stress_risk": "unknown",
            "frost_risk": "unknown",
            "gdd_adequacy": "unknown",
        }



        if "temperature_2m_mean" in df.columns:
            temps = df["temperature_2m_mean"].dropna()
            if temps.empty:
                return assessment

            mean_temp = temps.mean()
            if crop.min_temp_c <= mean_temp <= crop.max_temp_c:
                assessment["temperature_fit"] = "optimal"
            elif crop.min_temp_c - 5 <= mean_temp <= crop.max_temp_c + 5:
                assessment["temperature_fit"] = "marginal"
            else:
                assessment["temperature_fit"] = "poor"


  
            if "temperature_2m_max" in df.columns:
                t_max = df["temperature_2m_max"].dropna()
                hot_days = int((t_max > 35).sum())
                if hot_days > 10:
                    assessment["heat_stress_risk"] = "high"
                elif hot_days > 3:
                    assessment["heat_stress_risk"] = "moderate"
                else:
                    assessment["heat_stress_risk"] = "low"



   
            if "temperature_2m_min" in df.columns:
                t_min = df["temperature_2m_min"].dropna()
                frost_days = int((t_min < crop.frost_tolerance_c).sum())
                if frost_days > 5:
                    assessment["frost_risk"] = "high"
                elif frost_days > 0:
                    assessment["frost_risk"] = "moderate"
                else:
                    assessment["frost_risk"] = "low"


        if "temperature_2m_mean" in df.columns:
            t_mean = df["temperature_2m_mean"].dropna()
            gdd = (t_mean - 10).clip(lower=0).sum()
            gdd_ratio = gdd / crop.growing_degree_days if crop.growing_degree_days > 0 else 0
            if gdd_ratio >= 1.0:
                assessment["gdd_adequacy"] = "sufficient"
            elif gdd_ratio >= 0.8:
                assessment["gdd_adequacy"] = "marginal"
            else:
                assessment["gdd_adequacy"] = "insufficient"



        if "precipitation" in df.columns and "pet" in df.columns:
            total_precip = df["precipitation"].dropna().sum()
            total_pet = df["pet"].dropna().sum()
            water_ratio = total_precip / total_pet if total_pet > 0 else 0

            crop_water_need = crop.water_requirement_mm
            if total_precip >= crop_water_need * 0.8:
                assessment["water_fit"] = "adequate"
            elif total_precip >= crop_water_need * 0.5:
                assessment["water_fit"] = "supplemental irrigation needed"
            else:
                assessment["water_fit"] = "irrigation required"

            assessment["precipitation_mm"] = round(total_precip, 1)
            assessment["pet_mm"] = round(total_pet, 1)
            assessment["water_satisfaction_ratio"] = round(water_ratio, 2)

        return assessment

    async def fetch_climatology(self, location: Location) -> Dict:
        """Fetch long-term climatology for a location."""
        return await self.power.fetch_climatology(location)

    async def fetch_annual_summaries(
        self,
        location: Location,
        start_year: int,
        end_year: int,
    ) -> List[ClimateSummary]:
        """Fetch annual climate summaries for a range of years."""
        summaries = []
        for year in range(start_year, end_year + 1):
            try:
                summary = await self.power.fetch_annual_summary(location, year)
            except Exception as e:
                logger.error(f"Failed to fetch summary for {year}: {e}")
                continue


            if summary.mean_temp is None and summary.total_precipitation is None:
                logger.warning(f"No usable POWER data for {location} in {year}")
                continue

            summaries.append(summary)

        if not summaries:
            logger.warning(f"No usable POWER summaries for {location} {start_year}-{end_year}")

        return summaries

    async def fetch_recent_annual_summaries(
        self,
        location: Location,
        years: int = 5,
    ) -> List[ClimateSummary]:
        """Fetch the most recent `years` complete POWER annual summaries."""
        return await self.power.fetch_recent_annual_summaries(location, years=years)

    async def analyze_climate_trends(
        self,
        location: Location,
        years: int = 10,
    ) -> Dict:
        """Analyze climate trends over recent years."""
        summaries = await self.fetch_recent_annual_summaries(location, years=years)
        start_year = min(s.start_date.year for s in summaries)
        end_year = max(s.start_date.year for s in summaries)

        if len(summaries) < 3:
            return {"error": f"Need at least 3 years of data for a trend, got {len(summaries)}"}

        df = pd.DataFrame([s.model_dump() for s in summaries])
        df = df.select_dtypes(include="number")

        trends = {}
        for col in ["mean_temp", "total_precipitation", "total_pet", "aridity_index"]:
            if col in df.columns and df[col].notna().sum() > 2:
                x = df[col].dropna().reset_index(drop=True)
                n = len(x)
                if n > 1:

  
                    slope_per_decade = ((x - x.mean()) * (x.index - x.index.mean())).sum()
                    slope_per_decade /= ((x.index - x.index.mean()) ** 2).sum() * n / 10
                    trends[col] = {
                        "trend_per_decade": round(slope_per_decade, 2),
                        "direction": "increasing" if slope_per_decade > 0 else "decreasing",
                        "significance": "low", 
                        
                    }

        return {
            "period": f"{start_year}-{end_year}",
            "years_analyzed": len(summaries),
            "trends": trends,
            "mean_annual_temp": round(df["mean_temp"].dropna().mean(), 2) if "mean_temp" in df.columns else None,
            "mean_annual_precip": round(df["total_precipitation"].dropna().mean(), 1) if "total_precipitation" in df.columns else None,
        }

    async def get_climate_projections(
        self,
        location: Location,
        scenarios: List[str] = None,
    ) -> List[ClimateProjection]:
        """Assemble CMIP6-style projections for a location.

        NOTE: these values are SSP mid-point estimates for 2040-2060, not a
        live CMIP6/NEX-GDDP-CMIP6 download. Label them as scenario mid-points
        wherever they surface in the UI.
        """
        scenarios = scenarios or ["ssp245", "ssp585"]



        ssp_midpoints = {
            "ssp126": (1.8, 2),
            "ssp245": (2.0, 5),
            "ssp370": (2.4, 8),
            "ssp585": (3.5, 8),
        }

        projections = []
        for scenario in scenarios:
            temp_change, precip_change = ssp_midpoints.get(scenario, (2.0, 5))
            projections.append(
                ClimateProjection(
                    location_id=f"{location.latitude},{location.longitude}",
                    scenario=scenario,
                    model="ssp_midpoint_estimate",
                    period_start=2040,
                    period_end=2060,
                    temperature_change=temp_change,
                    precipitation_change_pct=precip_change,
                )
            )

        return projections

    async def close(self):
        """Close all API clients."""
        await self.power.close()
        await self.modis.close()
        await self.smap.close()
        await self.grace.close()