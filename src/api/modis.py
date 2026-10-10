"""NASA MODIS API client for vegetation indices and land surface data."""
from typing import Dict, List

import pandas as pd
from loguru import logger

from .base import NASAAPIClient, NASAAPIError
from ..models.location import Location


class MODISClient(NASAAPIClient):
    """Client for MODIS (Moderate Resolution Imaging Spectroradiometer) data."""

    BASE_URL = "https://modis.ornl.gov/rst/api/v1"
    RATE_LIMIT = 1.0
    CACHE_TTL = 86400 * 30  # 30 days

    # MODIS products relevant to agriculture
    PRODUCTS = {
        "NDVI": "MOD13Q1",      # 16-day NDVI at 250m
        "EVI": "MOD13Q1",       # 16-day EVI at 250m
        "LST_DAY": "MOD11A1",   # Daily land surface temp (day)
        "LST_NIGHT": "MOD11A1", # Daily land surface temp (night)
        "LAI": "MOD15A2H",      # 8-day Leaf Area Index at 500m
        "FPAR": "MOD15A2H",     # 8-day FPAR at 500m
        "GPP": "MOD17A2H",      # 8-day Gross Primary Production at 500m
        "NPP": "MOD17A3H",      # Annual Net Primary Production at 500m
        "ET": "MOD16A2",        # 8-day Evapotranspiration at 500m
        "ALBEDO": "MCD43A3",    # Daily Albedo at 500m
    }

    BANDS = {
        "NDVI": "250m_16_days_NDVI",
        "EVI": "250m_16_days_EVI",
        "LST_DAY": "LST_Day_1km",
        "LST_NIGHT": "LST_Night_1km",
        "LAI": "Lai_500m",
        "FPAR": "Fpar_500m",
        "GPP": "Gpp_500m",
        "NPP": "Npp_500m",
        "ET": "ET_500m",
        "ALBEDO": "Albedo_BSA_Band1",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def fetch_climate_data(self, location: Location, start_date: str, end_date: str) -> Dict:
        """Fetch MODIS vegetation and land surface data."""
        return await self.fetch_time_series(location, start_date, end_date, ["NDVI", "EVI", "LST_DAY"])

    async def fetch_time_series(
        self,
        location: Location,
        start_date: str,
        end_date: str,
        variables: List[str],
    ) -> Dict:
        """
        Fetch time series for multiple MODIS variables.

        Args:
            location: Geographic location
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            variables: List of variable names (NDVI, EVI, LST_DAY, etc.)

        Returns:
            Dictionary with variable names as keys and time series data
        """
        results = {}

        for var in variables:
            if var not in self.PRODUCTS:
                logger.warning(f"Unknown MODIS variable: {var}")
                continue

            try:
                data = await self._fetch_single_variable(location, start_date, end_date, var)
                results[var] = data
            except Exception as e:
                logger.error(f"Failed to fetch {var}: {e}")
                results[var] = {"error": str(e)}

        return results

    async def _fetch_single_variable(
        self,
        location: Location,
        start_date: str,
        end_date: str,
        variable: str,
    ) -> Dict:
        """Fetch time series for a single MODIS variable."""
        product = self.PRODUCTS[variable]
        band = self.BANDS[variable]

        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "product": product,
            "band": band,
            "start": start_date,
            "end": end_date,
            "format": "json",
        }

        response = await self.request(f"subset", params)
        return self._parse_subset_response(response, variable)

    def _parse_subset_response(self, response: Dict, variable: str) -> Dict:
        """Parse MODIS subset API response."""
        if "subset" not in response:
            return {"error": "No subset data in response"}

        subset = response["subset"]
        if not subset:
            return {"error": "Empty subset"}

        data = subset[0].get("data", {})
        if not data:
            return {"error": "No data in subset"}

        # Extract time series
        time_series = []
        band = subset[0].get("bands", [{}])[0] if isinstance(subset[0].get("bands"), list) else {}
        scale = band.get("scale", subset[0].get("scale", 1.0))
        fill_value = band.get("fill_value", subset[0].get("fill_value", -3000))

        for date_str, value in data.items():
            try:
                # MODIS dates look like A2023001 (year + day of year)
                if not (date_str.startswith("A") and len(date_str) == 8):
                    continue

                # Apply scale/fill values reported by the API
                if value == fill_value:
                    value = None
                elif value is not None:
                    value = value * scale

                time_series.append({"date": date_str, "value": value})
            except (TypeError, ValueError) as e:
                logger.warning(f"Skipping MODIS record {date_str}: {e}")

        time_series.sort(key=lambda p: p["date"])

        valid = [p["value"] for p in time_series if p.get("value") is not None]
        if not valid:
            return {
            "variable": variable,
            "product": self.PRODUCTS[variable],
            "unit": self._get_unit(variable),
            "error": "No valid values (pixel may be water or masked)",
            "data": [],
        }

        return {
            "variable": variable,
            "product": self.PRODUCTS[variable],
            "unit": self._get_unit(variable),
            "data": time_series,
        }

    def _get_unit(self, variable: str) -> str:
        units = {
            "NDVI": "index (-1 to 1)",
            "EVI": "index (-1 to 1)",
            "LST_DAY": "Kelvin",
            "LST_NIGHT": "Kelvin",
            "LAI": "m²/m²",
            "FPAR": "fraction (0-1)",
            "GPP": "kg C/m²/8day",
            "NPP": "kg C/m²/year",
            "ET": "kg/m²/8day",
            "ALBEDO": "fraction (0-1)",
        }
        return units.get(variable, "unknown")

    async def fetch_annual_composite(
        self,
        location: Location,
        year: int,
        variable: str = "NDVI",
    ) -> Dict:
        """Fetch annual composite (e.g., max NDVI, mean LST)."""
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        return await self._fetch_single_variable(location, start, end, variable)

    async def fetch_phenology_metrics(
        self,
        location: Location,
        year: int,
    ) -> Dict:
        """Derive phenology metrics from NDVI/EVI time series."""
        ndvi_data = await self.fetch_annual_composite(location, year, "NDVI")
        evi_data = await self.fetch_annual_composite(location, year, "EVI")

        metrics = {}

        for var_name, data in [("NDVI", ndvi_data), ("EVI", evi_data)]:
            if "data" not in data:
                continue

            series = [(d["date"], d["value"]) for d in data["data"] if d.get("value") is not None]
            if not series:
                continue

            values = [v for _, v in series]

            metrics[f"{var_name}_mean"] = round(sum(values) / len(values), 4)
            metrics[f"{var_name}_max"] = round(max(values), 4)
            metrics[f"{var_name}_min"] = round(min(values), 4)
            metrics[f"{var_name}_amplitude"] = round(max(values) - min(values), 4)

            # Start/end of season: first/last crossing of 30% above the minimum
            threshold = min(values) + 0.3 * (max(values) - min(values))
            sos = next((dt for dt, v in series if v > threshold), None)
            eos = next((dt for dt, v in reversed(series) if v > threshold), None)

            if sos:
                metrics[f"{var_name}_sos"] = sos
            if eos:
                metrics[f"{var_name}_eos"] = eos

        return metrics