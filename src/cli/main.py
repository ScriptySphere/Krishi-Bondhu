"""Main CLI application for the crop rotation decision support tool."""
import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

from ..models.location import Location
from ..models.soil import SoilProfile, SoilLayer, SoilTexture
from ..models.climate import ClimateSummary
from ..models.crop import CropType
from ..models.recommendation import Priority, RotationComparison
from ..services.crop_service import CropService
from ..services.soil_service import SoilService
from ..services.climate_service import ClimateService
from ..services.rotation_service import RotationService
from ..services.recommendation_service import RecommendationService
from ..api.power import POWERClient
from ..api.modis import MODISClient

app = typer.Typer(
    name="crop-rotation",
    help="NASA-powered crop rotation decision support tool",
    add_completion=False,
)
console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        lambda msg: console.print(msg, end=""),
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )


@app.callback()
def callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    nasa_key: Optional[str] = typer.Option(None, "--nasa-key", envvar="NASA_API_KEY", help="NASA API key"),
):
    """NASA Crop Rotation Decision Support Tool."""
    setup_logging(verbose)
    if nasa_key:
        logger.info("NASA API key provided")


@app.command()
def analyze(
    latitude: float = typer.Option(..., "--lat", help="Latitude"),
    longitude: float = typer.Option(..., "--lon", help="Longitude"),
    start_year: int = typer.Option(2020, "--start-year", help="Start year for climate data"),
    end_year: int = typer.Option(2024, "--end-year", help="End year for climate data"),
    years: int = typer.Option(3, "--years", help="Rotation length in years"),
    priorities: List[str] = typer.Option(
        ["yield", "soil_health", "water_conservation"],
        "--priority",
        "-p",
        help="Farmer priorities (yield, soil_health, water_conservation, risk_reduction, profitability, climate_adaptation)",
    ),
    max_results: int = typer.Option(10, "--max-results", help="Maximum recommendations to show"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (JSON or CSV)"),
    format: str = typer.Option("json", "--format", help="Output format (json, csv)"),
):
    """Analyze location and generate crop rotation recommendations."""

    async def run_analysis():
        location = Location(latitude=latitude, longitude=longitude)

        console.print(Panel.fit(
            f"[bold]Crop Rotation Analysis[/bold]\n"
            f"Location: {location.latitude:.4f}, {location.longitude:.4f}\n"
            f"Period: {start_year}-{end_year}\n"
            f"Rotation length: {years} years",
            title="Configuration",
        ))

        # Initialize services
        power_client = POWERClient()
        modis_client = MODISClient()
        climate_service = ClimateService(power_client=power_client, modis_client=modis_client)
        crop_service = CropService()
        soil_service = SoilService()
        rotation_service = RotationService(soil_service=soil_service, climate_service=climate_service)
        recommendation_service = RecommendationService(
            rotation_service=rotation_service,
            crop_service=crop_service,
            soil_service=soil_service,
        )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Fetch climate data
                task = progress.add_task("Fetching climate data...", total=None)
                start_date = f"{start_year}-01-01"
                end_date = f"{end_year}-12-31"

                climate_data = await climate_service.fetch_comprehensive_climate(
                    location, start_date, end_date
                )

                # Get annual summaries
                summaries = await climate_service.fetch_annual_summaries(
                    location, start_year, end_year
                )
                if summaries:
                    # Average across years
                    climate_summary = ClimateSummary(
                        location_id=f"{location.latitude},{location.longitude}",
                        start_date=date(start_year, 1, 1),
                        end_date=date(end_year, 12, 31),
                        mean_temp=sum(s.mean_temp or 0 for s in summaries) / len(summaries),
                        total_precipitation=sum(s.total_precipitation or 0 for s in summaries) / len(summaries),
                        total_pet=sum(s.total_pet or 0 for s in summaries) / len(summaries),
                        aridity_index=sum(s.aridity_index or 0 for s in summaries) / len(summaries),
                        growing_degree_days=int(sum(s.growing_degree_days or 0 for s in summaries) / len(summaries)),
                        frost_days=int(sum(s.frost_days or 0 for s in summaries) / len(summaries)),
                        heat_stress_days=int(sum(s.heat_stress_days or 0 for s in summaries) / len(summaries)),
                    )
                else:
                    climate_summary = None

                progress.update(task, description="Analyzing soil...")

                # Create a default soil profile if none provided
                soil_profile = create_default_soil_profile(location)

                progress.update(task, description="Generating recommendations...")

                # Parse priorities
                priority_enums = [Priority(p) for p in priorities]

                # Generate recommendations
                comparison = recommendation_service.generate_recommendations(
                    location=location,
                    soil_profile=soil_profile,
                    climate_summary=climate_summary,
                    priorities=priority_enums,
                    years=years,
                    max_recommendations=max_results,
                )

                progress.update(task, description="Complete!")

            # Display results
            console.print("\n")
            console.print(recommendation_service.format_recommendation_summary(comparison, top_n=max_results))

            # Export if requested
            if output:
                recommendation_service.export_recommendations(comparison, output, format)
                console.print(f"\n[green]Results exported to {output}[/green]")

        finally:
            await climate_service.close()

    asyncio.run(run_analysis())


def create_default_soil_profile(location: Location) -> SoilProfile:
    """Create a default soil profile for demonstration."""
    layers = [
        SoilLayer(
            depth_top=0,
            depth_bottom=20,
            texture=SoilTexture.LOAM,
            organic_carbon=2.5,
            ph=6.5,
            bulk_density=1.35,
            nitrogen=0.15,
            phosphorus=25,
            potassium=180,
            cec=20,
            available_water_capacity=0.20,
        ),
        SoilLayer(
            depth_top=20,
            depth_bottom=50,
            texture=SoilTexture.CLAY_LOAM,
            organic_carbon=1.2,
            ph=6.8,
            bulk_density=1.45,
            nitrogen=0.08,
            phosphorus=15,
            potassium=150,
            cec=25,
            available_water_capacity=0.20,
        ),
        SoilLayer(
            depth_top=50,
            depth_bottom=100,
            texture=SoilTexture.CLAY,
            organic_carbon=0.5,
            ph=7.2,
            bulk_density=1.50,
            nitrogen=0.03,
            phosphorus=8,
            potassium=120,
            cec=30,
            available_water_capacity=0.16,
        ),
    ]

    return SoilProfile(
        location_id=f"{location.latitude},{location.longitude}",
        layers=layers,
        drainage_class="well_drained",
        taxonomic_class="Typic Hapludalf",
        source="default_template",
    )


@app.command()
def climate(
    latitude: float = typer.Option(..., "--lat", help="Latitude"),
    longitude: float = typer.Option(..., "--lon", help="Longitude"),
    start_date: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Fetch and display climate data for a location."""

    async def run_climate():
        location = Location(latitude=latitude, longitude=longitude)

        power_client = POWERClient()
        climate_service = ClimateService(power_client=power_client)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching climate data...", total=None)

            daily_data = await climate_service.power.fetch_climate_data(
                location, start_date, end_date
            )

            summary = climate_service._summarize_power(daily_data)

            progress.update(task, description="Complete!")

        # Display summary
        table = Table(title=f"Climate Summary: {location}")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")

        for key, value in summary.items():
            if isinstance(value, dict):
                table.add_row(key, f"mean: {value.get('mean', 'N/A')}, min: {value.get('min', 'N/A')}, max: {value.get('max', 'N/A')}")
            else:
                table.add_row(key, str(value))

        console.print(table)

        if output:
            import json
            with open(output, "w") as f:
                json.dump(summary, f, indent=2, default=str)
            console.print(f"[green]Data exported to {output}[/green]")

        await climate_service.close()

    asyncio.run(run_climate())


@app.command()
def crops(
    crop_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by crop type"),
    list_types: bool = typer.Option(False, "--list-types", help="List available crop types"),
):
    """List available crops in the database."""
    crop_service = CropService()

    if list_types:
        console.print("Available crop types:")
        for ct in CropType:
            console.print(f"  {ct.value}")
        return

    crops = crop_service.list_crops(
        CropType(crop_type) if crop_type else None
    )

    table = Table(title="Crop Database")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Water (mm)", justify="right")
    table.add_column("N Fix (kg/ha)", justify="right")
    table.add_column("N Uptake (kg/ha)", justify="right")
    table.add_column("Root Depth (cm)", justify="right")
    table.add_column("Drought Tol.", justify="right")
    table.add_column("Soil Health", justify="right")
    table.add_column("Market ($/t)", justify="right")

    for crop in crops:
        table.add_row(
            crop.name,
            crop.crop_type.value,
            str(crop.water_requirement_mm),
            str(crop.n_fixation_kg_ha),
            str(crop.n_uptake_kg_ha),
            str(crop.root_depth_cm),
            str(crop.drought_tolerance),
            str(crop.soil_health_index),
            str(crop.market_value_usd_ton or "N/A"),
        )

    console.print(table)


@app.command()
def soil(
    latitude: float = typer.Option(..., "--lat", help="Latitude"),
    longitude: float = typer.Option(..., "--lon", help="Longitude"),
):
    """Analyze default soil profile for a location."""
    location = Location(latitude=latitude, longitude=longitude)
    soil_service = SoilService()

    profile = create_default_soil_profile(location)
    analysis = soil_service.analyze_profile(profile)

    console.print(Panel.fit(
        f"[bold]Soil Profile Analysis[/bold]\n"
        f"Location: {location}\n"
        f"Max Depth: {analysis['max_depth_cm']} cm\n"
        f"Total SOC: {analysis['total_soc_t_ha']} t/ha\n"
        f"Average pH: {analysis['average_ph']}\n"
        f"Plant Available Water: {analysis['plant_available_water_mm']} mm\n"
        f"Drainage: {analysis['drainage_class']}",
        title="Soil Summary",
    ))

    # Nutrient status
    table = Table(title="Nutrient Status")
    table.add_column("Nutrient", style="cyan")
    table.add_column("Status", style="green")
    for nutrient, status in analysis["nutrient_status"].items():
        table.add_row(nutrient.capitalize(), status)
    console.print(table)

    # Constraints
    if analysis["constraints"]:
        console.print("\n[bold yellow]Constraints:[/bold yellow]")
        for constraint in analysis["constraints"]:
            console.print(f"  • {constraint}")
    else:
        console.print("\n[green]No major constraints identified[/green]")


@app.command()
def rotation(
    name: str = typer.Option(..., "--name", "-n", help="Rotation name"),
    crops: List[str] = typer.Option(..., "--crop", "-c", help="Crop names in sequence"),
    latitude: float = typer.Option(..., "--lat", help="Latitude"),
    longitude: float = typer.Option(..., "--lon", help="Longitude"),
    start_year: int = typer.Option(2020, "--start-year", help="Climate data start year"),
    end_year: int = typer.Option(2024, "--end-year", help="Climate data end year"),
):
    """Evaluate a specific crop rotation."""
    location = Location(latitude=latitude, longitude=longitude)

    crop_service = CropService()
    rotation = crop_service.create_custom_rotation(name, crops, f"{latitude},{longitude}")

    if not rotation:
        console.print("[red]Failed to create rotation - check crop names[/red]")
        raise typer.Exit(1)

    # Get climate data
    async def get_climate():
        power_client = POWERClient()
        climate_service = ClimateService(power_client=power_client)
        summaries = await climate_service.fetch_annual_summaries(
            location, start_year, end_year
        )
        await climate_service.close()
        return summaries

    summaries = asyncio.run(get_climate())

    if summaries:
        climate_summary = ClimateSummary(
            location_id=f"{location.latitude},{location.longitude}",
            start_date=date(start_year, 1, 1),
            end_date=date(end_year, 12, 31),
            mean_temp=sum(s.mean_temp or 0 for s in summaries) / len(summaries),
            total_precipitation=sum(s.total_precipitation or 0 for s in summaries) / len(summaries),
            total_pet=sum(s.total_pet or 0 for s in summaries) / len(summaries),
            aridity_index=sum(s.aridity_index or 0 for s in summaries) / len(summaries),
            growing_degree_days=int(sum(s.growing_degree_days or 0 for s in summaries) / len(summaries)),
            frost_days=int(sum(s.frost_days or 0 for s in summaries) / len(summaries)),
            heat_stress_days=int(sum(s.heat_stress_days or 0 for s in summaries) / len(summaries)),
        )
    else:
        climate_summary = None

    soil_service = SoilService()
    soil_profile = create_default_soil_profile(location)

    rotation_service = RotationService(soil_service=soil_service)
    evaluation = rotation_service.evaluate_rotation(rotation, soil_profile, climate_summary, location)

    console.print(rotation_service.generate_rotation_report(
        rotation, soil_profile, climate_summary, location
    ))


@app.command()
def demo(
    latitude: float = typer.Option(40.7128, "--lat", help="Latitude"),
    longitude: float = typer.Option(-74.0060, "--lon", help="Longitude"),
):
    """Run a quick demo with default settings."""
    console.print(Panel.fit(
        "[bold green]NASA Crop Rotation Decision Support Tool - Demo[/bold green]\n\n"
        "This demo shows the tool capabilities with sample data.\n"
        "For real analysis, use the 'analyze' command with your location.",
        title="Demo Mode",
    ))

    # Run analysis with defaults
    from typer.main import get_command
    ctx = typer.Context(app)
    ctx.invoke(analyze, latitude=latitude, longitude=longitude, years=3, max_results=5)


if __name__ == "__main__":
    app()