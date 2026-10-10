# NASA Crop Rotation Decision Support Tool

A decision-support tool that uses NASA Earth observations along with local soil information, crop characteristics, and farmer priorities to help farmers explore rotation strategies that strengthen soil health and adapt farms to changing conditions.

## Features

- **NASA Earth Data Integration**: Leverages NASA POWER, MODIS, SMAP, and GRACE APIs for climate, soil moisture, and water availability data
- **Soil Health Analysis**: Evaluates soil organic carbon, pH, nutrient levels, and structure
- **Crop Rotation Optimization**: Recommends rotations based on nitrogen fixation, pest breaks, water use efficiency, and market value
- **Climate Adaptation**: Projects future conditions using NASA climate projections
- **Farmer-Centric**: Incorporates local priorities (yield, water conservation, soil building, risk reduction)

source .venv/bin/activate
python web/run.py

## Architecture

```
src/
├── api/           # NASA API clients
├── models/        # Data models and schemas
├── services/      # Business logic services
├── cli/           # Command-line interface
└── utils/         # Utilities and helpers
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your NASA API key

# Run the tool
python -m src.cli.main --help
```

## NASA APIs Used

- **NASA POWER**: Solar and meteorological data (temperature, precipitation, humidity, wind)
- **MODIS**: Land surface temperature, vegetation indices (NDVI, EVI)
- **SMAP**: Soil moisture data
- **GRACE**: Groundwater storage changes
- **Daymet**: Daily weather parameters

## License

MIT
