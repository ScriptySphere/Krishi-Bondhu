"""NASA POWER API client for meteorological and solar data."""
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from .base import NASAAPIClient, NASAAPIError
from ..models.location import Location
from ..models.climate import ClimateData, ClimateVariable, ClimateSummary

__all__ = ["POWERClient", "NASAAPIError"]


class POWERClient(NASAAPIClient):
    """Client for NASA POWER (Prediction Of Worldwide Energy Resources) API."""

    BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
    RATE_LIMIT = 2.0  # 2 requests per second
    CACHE_TTL = 86400 * 7  # 1 week

    # Available parameters from POWER (AG community)
    # Note: EVAPOTRANSPIRATION and PET are not valid POWER parameters and
    # cause a 422 error. They are omitted here.
    PARAMETERS = {
        ClimateVariable.TEMPERATURE_2M: "T2M",
        ClimateVariable.TEMPERATURE_2M_MAX: "T2M_MAX",
        ClimateVariable.TEMPERATURE_2M_MIN: "T2M_MIN",
        ClimateVariable.PRECIPITATION: "PRECTOTCORR",
        ClimateVariable.RELATIVE_HUMIDITY: "RH2M",
        ClimateVariable.WIND_SPEED_10M: "WS10M",
        ClimateVariable.SOLAR_RADIATION: "ALLSKY_SFC_SW_DWN",
        ClimateVariable.PAR: "ALLSKY_SFC_PAR_TOT",
        ClimateVariable.SOIL_MOISTURE_0_10CM: "GWETTOP",
        ClimateVariable.SOIL_MOISTURE_10_40CM: "GWETROOT",
        ClimateVariable.SOIL_MOISTURE_40_100CM: "GWETPROF",
    }

    def __init__(self, base_url: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if base_url:
            self.BASE_URL = base_url
        self.community = "AG"  # Agroclimatology community

    async def fetch_climate_data(
        self,
        location: Location,
        start_date: str,
        end_date: str,
        parameters: Optional[List[ClimateVariable]] = None,
    ) -> List[ClimateData]:
        """
        Fetch daily climate data for a location and date range.

        Args:
            location: Geographic location
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            parameters: Specific climate variables to fetch (default: all)

        Returns:
            List of ClimateData objects
        """
        params = parameters or list(self.PARAMETERS.keys())
        param_string = ",".join(self.PARAMETERS[p] for p in params)

        query_params = {
            "parameters": param_string,
            "community": self.community,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start": start_date.replace("-", ""),
            "end": end_date.replace("-", ""),
            "format": "JSON",
        }

        if self.api_key:
            query_params["api_key"] = self.api_key

        try:
            response = await self.request("", query_params)
            return self._parse_response(response, location, params)
        except NASAAPIError:
            raise
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"POWER API parsing error: {e}")
            raise NASAAPIError(f"Failed to parse POWER response: {e}") from e

    def _parse_response(
        self,
        response: Dict,
        location: Location,
        requested_params: List[ClimateVariable],
    ) -> List[ClimateData]:
        """Parse POWER API response into ClimateData objects."""
        if not isinstance(response, dict):
            raise NASAAPIError("POWER returned an unexpected payload")

        properties = response.get("properties", {})
        parameter_data = properties.get("parameter", {})

        # Dates come from the first requested parameter
        param_key = self.PARAMETERS[requested_params[0]]
        dates = list(parameter_data.get(param_key, {}).keys())

        if not dates:
            raise NASAAPIError("POWER response contained no daily records")

        location_id = f"{location.latitude},{location.longitude}"
        climate_records = []

        for date_str in dates:
            try:
                dt = datetime.strptime(date_str, "%Y%m%d").date()
                record = ClimateData(location_id=location_id, date=dt)

                for param in requested_params:
                    key = self.PARAMETERS[param]
                    value = parameter_data.get(key, {}).get(date_str)

                    # POWER encodes missing values as -999
                    if value == -999:
                        value = None

                    self._set_climate_field(record, param, value)

                climate_records.append(record)
            except ValueError:
                logger.warning(f"Skipping POWER record with unparseable date {date_str}")
                continue

        return sorted(climate_records, key=lambda x: x.date)

    def _set_climate_field(self, record: ClimateData, param: ClimateVariable, value: Optional[float]):
        """Set the appropriate field on ClimateData based on parameter."""
        mapping = {
            ClimateVariable.TEMPERATURE_2M: "temperature_2m_mean",
            ClimateVariable.TEMPERATURE_2M_MAX: "temperature_2m_max",
            ClimateVariable.TEMPERATURE_2M_MIN: "temperature_2m_min",
            ClimateVariable.PRECIPITATION: "precipitation",
            ClimateVariable.RELATIVE_HUMIDITY: "relative_humidity",
            ClimateVariable.WIND_SPEED_10M: "wind_speed_10m",
            ClimateVariable.SOLAR_RADIATION: "solar_radiation",
            ClimateVariable.PAR: "par",
            ClimateVariable.SOIL_MOISTURE_0_10CM: "soil_moisture_surface",
            ClimateVariable.SOIL_MOISTURE_10_40CM: "soil_moisture_root",
            ClimateVariable.SOIL_MOISTURE_40_100CM: "soil_moisture_profile",
            ClimateVariable.EVAPOTRANSPIRATION: "evapotranspiration",
            ClimateVariable.PET: "pet",
        }

        field = mapping.get(param)
        if not field:
            return

        # POWER occasionally returns values outside a field's valid range
        # (e.g. soil wetness slightly above 1). Drop those rather than
        # discarding the whole daily record.
        if value is not None:
            try:
                setattr(record, field, value)
            except ValueError:
                logger.debug(f"Dropping out-of-range {field}={value}")
                setattr(record, field, None)

    async def fetch_climatology(
        self,
        location: Location,
        parameters: Optional[List[ClimateVariable]] = None,
    ) -> Dict:
        """
        Fetch long-term climatology (1984-present averages).

        Returns monthly averages for each parameter.
        """
        params = parameters or list(self.PARAMETERS.keys())
        param_string = ",".join(self.PARAMETERS[p] for p in params)

        query_params = {
            "parameters": param_string,
            "community": self.community,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "format": "JSON",
            "temporal-average": "MONTHLY",
        }

        if self.api_key:
            query_params["api_key"] = self.api_key

        response = await self.request("", query_params)
        return self._parse_climatology(response, params)

    def _parse_climatology(self, response: Dict, requested_params: List[ClimateVariable]) -> Dict:
        """Parse climatology response."""
        properties = response.get("properties", {})
        parameter_data = properties.get("parameter", {})

        result = {}
        for param in requested_params:
            key = self.PARAMETERS[param]
            monthly = parameter_data.get(key, {})
            try:
                # POWER keys these by year for monthly climatology (e.g. "1998")
                months = {
                    int(k[4:]): v for k, v in monthly.items() if len(k) >= 6 and v != -999
                }
            except (TypeError, ValueError):
                continue

            if months:
                result[param.value] = months

        return result

    async def fetch_annual_summary(
        self,
        location: Location,
        year: int,
    ) -> ClimateSummary:
        """Fetch and compute annual climate summary for a year."""
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        daily_data = await self.fetch_climate_data(location, start_date, end_date)
        return self._compute_summary(location, daily_data, start_date, end_date)

    async def fetch_recent_annual_summaries(
        self,
        location: Location,
        years: int = 5,
    ) -> List[ClimateSummary]:
        """
        Fetch the most recent `years` complete annual summaries.

        POWER lags before the current year is complete, so walk backwards until
        enough years return usable data. Years filled entirely with -999 (no
        coverage for that pixel) are skipped rather than averaged in as zeros.
        """
        current_year = datetime.now().year - 1
        collected: List[ClimateSummary] = []
        last_error: Optional[str] = None

        for year in range(current_year, current_year - years * 2, -1):
            if len(collected) >= years:
                break
            try:
                summary = await self.fetch_annual_summary(location, year)
            except Exception as e:
                last_error = str(e)
                logger.warning(f"POWER {year} unavailable for {location}: {e}")
                continue

            if summary.mean_temp is None and summary.total_precipitation is None:
                last_error = f"POWER {year} returned only fill values (-999) for {location}"
                logger.warning(last_error)
                continue

            collected.append(summary)

        if not collected:
            raise NASAAPIError(
                last_error or f"No usable POWER data for {location}"
            )

        collected.sort(key=lambda s: s.start_date)
        return collected

    def _compute_summary(
        self,
        location: Location,
        daily_data: List[ClimateData],
        start_date: str,
        end_date: str,
    ) -> ClimateSummary:
        """Compute summary statistics from daily data."""
        if not daily_data:
            return ClimateSummary(
                location_id=f"{location.latitude},{location.longitude}",
                start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
                end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
            )

        df = pd.DataFrame([d.model_dump() for d in daily_data])
        df = df.select_dtypes(include="number")

        # POWER encodes missing values as -999; treat them as absent, not real
        df = df.replace(-999.0, float("nan")).astype(float)

        summary = ClimateSummary(
            location_id=f"{location.latitude},{location.longitude}",
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
        )

        if "temperature_2m_mean" in df.columns:
            t_mean = df["temperature_2m_mean"].dropna()
            summary.mean_temp = round(t_mean.mean(), 2) if len(t_mean) else None

        if "temperature_2m_max" in df.columns:
            t_max = df["temperature_2m_max"].dropna()
            summary.max_temp = round(t_max.max(), 2) if len(t_max) else None
            summary.heat_stress_days = int((t_max > 35).sum()) if len(t_max) else None

        if "temperature_2m_min" in df.columns:
            t_min = df["temperature_2m_min"].dropna()
            summary.min_temp = round(t_min.min(), 2) if len(t_min) else None
            summary.frost_days = int((t_min < 0).sum()) if len(t_min) else None

        if "temperature_2m_mean" in df.columns:
            t_mean = df["temperature_2m_mean"].dropna()
            # Growing degree days, base 10°C
            summary.growing_degree_days = int((t_mean - 10).clip(lower=0).sum()) if len(t_mean) else None

        if "precipitation" in df.columns:
            precip = df["precipitation"].dropna()
            summary.total_precipitation = round(precip.sum(), 2) if len(precip) else None

        if "relative_humidity" in df.columns:
            humidity = df["relative_humidity"].dropna()
            summary.mean_humidity = round(humidity.mean(), 2) if len(humidity) else None

        if "evapotranspiration" in df.columns:
            et = df["evapotranspiration"].dropna()
            summary.total_et = round(et.sum(), 2) if len(et) else None

        if "pet" in df.columns:
            pet = df["pet"].dropna()
            summary.total_pet = round(pet.sum(), 2) if len(pet) else None

        # POWER's PET parameter is not available for the AG community, so fall
        # back to the Hargreaves equation (FAO-56) using the daily temperature
        # range we did fetch. This is a standard reference-ET estimate, not a
        # made-up number.
        if not summary.total_pet and {"temperature_2m_mean", "temperature_2m_max", "temperature_2m_min"} <= set(df.columns):
            summary.total_pet = round(self._hargreaves_annual_et0(df, daily_data, location.latitude), 2)

        # Aridity: potential evapotranspiration relative to rainfall
        if summary.total_pet and summary.total_precipitation:
            summary.aridity_index = round(summary.total_pet / summary.total_precipitation, 2)

        return summary

    @staticmethod
    def _hargreaves_annual_et0(df: "pd.DataFrame", daily_data: List["ClimateData"], latitude: float) -> float:
        """
        Annual reference evapotranspiration (mm) via the Hargreaves equation.

        FAO-56 eq. 52: ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * Ra
        with Ra (extraterrestrial radiation) derived from latitude and day of
        year. Used only because POWER's PET parameter is unavailable for the
        AG community.
        """
        import math

        GSC = 0.0820  # solar constant, MJ m-2 min-1
        LATENT_HEAT = 2.45  # MJ kg-1, converts Ra to mm of water

        t_mean = df["temperature_2m_mean"]
        t_max = df["temperature_2m_max"]
        t_min = df["temperature_2m_min"]

        # Day of year per record, aligned to the numeric frame's row order
        doy = pd.Series(
            [d.date.timetuple().tm_yday for d in daily_data],
            index=df.index,
        )

        phi = math.radians(latitude)
        total = 0.0

        for i in df.index:
            tm, tx, tn = t_mean.get(i), t_max.get(i), t_min.get(i)
            if tm is None or tx is None or tn is None:
                continue
            if any(pd.isna(v) for v in (tm, tx, tn)):
                continue
            if tx < tn:
                continue

            j = int(doy.get(i, 1))
            dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * j)
            decl = 0.409 * math.sin(2 * math.pi / 365 * j - 1.39)
            ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))
            ra = (24 * 60 / math.pi) * GSC * dr * (
                ws * math.sin(phi) * math.sin(decl)
                + math.cos(phi) * math.cos(decl) * math.sin(ws)
            ) / LATENT_HEAT  # mm/day

            total += 0.0023 * (tm + 17.8) * math.sqrt(tx - tn) * ra

        return total