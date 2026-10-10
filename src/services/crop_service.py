"""Crop database and management service."""
from typing import Dict, List, Optional
from pathlib import Path
import json

from loguru import logger

from ..models.crop import (
    Crop,
    CropCharacteristics,
    CropRotation,
    CropType,
    GrowthHabit,
)


class CropService:
    """Service for crop data management and rotation generation."""

    def __init__(self, crop_database_path: Optional[Path] = None):
        self.crop_database: Dict[str, CropCharacteristics] = {}
        self._load_default_crops()
        if crop_database_path and crop_database_path.exists():
            self.load_database(crop_database_path)

    def _load_default_crops(self):
        """Load built-in crop database."""
        default_crops = [


          
            CropCharacteristics(
                name="Maize",
                scientific_name="Zea mays",
                crop_type=CropType.CEREAL,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=500,
                drought_tolerance=3,
                irrigation_response=1.3,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=180,
                p_uptake_kg_ha=35,
                k_uptake_kg_ha=160,
                residue_cn_ratio=50,
                root_depth_cm=100,
                biomass_kg_ha=12000,
                soil_health_index=-1,
                min_temp_c=10,
                max_temp_c=38,
                optimal_temp_c=25,
                frost_tolerance_c=-2,
                growing_degree_days=1300,
                pest_break_value=1,
                market_value_usd_ton=180,
                production_cost_usd_ha=600,
            ),
            CropCharacteristics(
                name="Wheat",
                scientific_name="Triticum aestivum",
                crop_type=CropType.CEREAL,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=450,
                drought_tolerance=3,
                irrigation_response=1.2,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=150,
                p_uptake_kg_ha=30,
                k_uptake_kg_ha=120,
                residue_cn_ratio=80,
                root_depth_cm=120,
                biomass_kg_ha=10000,
                soil_health_index=-1,
                min_temp_c=3,
                max_temp_c=32,
                optimal_temp_c=20,
                frost_tolerance_c=-10,
                growing_degree_days=1100,
                pest_break_value=1,
                market_value_usd_ton=220,
                production_cost_usd_ha=450,
            ),
            CropCharacteristics(
                name="Rice",
                scientific_name="Oryza sativa",
                crop_type=CropType.CEREAL,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=1200,
                drought_tolerance=1,
                irrigation_response=1.5,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=120,
                p_uptake_kg_ha=25,
                k_uptake_kg_ha=140,
                residue_cn_ratio=70,
                root_depth_cm=50,
                biomass_kg_ha=11000,
                soil_health_index=-1,
                min_temp_c=15,
                max_temp_c=38,
                optimal_temp_c=28,
                frost_tolerance_c=0,
                growing_degree_days=1400,
                pest_break_value=0,
                market_value_usd_ton=350,
                production_cost_usd_ha=800,
            ),



      
            CropCharacteristics(
                name="Soybean",
                scientific_name="Glycine max",
                crop_type=CropType.LEGUME,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=450,
                drought_tolerance=3,
                irrigation_response=1.2,
                n_fixation_kg_ha=150,
                n_uptake_kg_ha=200,
                p_uptake_kg_ha=25,
                k_uptake_kg_ha=100,
                residue_cn_ratio=30,
                root_depth_cm=80,
                biomass_kg_ha=6000,
                soil_health_index=2,
                min_temp_c=10,
                max_temp_c=35,
                optimal_temp_c=26,
                frost_tolerance_c=-1,
                growing_degree_days=1200,
                pest_break_value=3,
                disease_susceptibility={"SCN": 3, "white_mold": 2},
                market_value_usd_ton=450,
                production_cost_usd_ha=500,
            ),
            CropCharacteristics(
                name="Common Bean",
                scientific_name="Phaseolus vulgaris",
                crop_type=CropType.LEGUME,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=350,
                drought_tolerance=3,
                irrigation_response=1.1,
                n_fixation_kg_ha=80,
                n_uptake_kg_ha=120,
                p_uptake_kg_ha=20,
                k_uptake_kg_ha=90,
                residue_cn_ratio=25,
                root_depth_cm=60,
                biomass_kg_ha=4000,
                soil_health_index=1,
                min_temp_c=10,
                max_temp_c=32,
                optimal_temp_c=22,
                frost_tolerance_c=-1,
                growing_degree_days=900,
                pest_break_value=2,
                market_value_usd_ton=800,
                production_cost_usd_ha=600,
            ),
            CropCharacteristics(
                name="Chickpea",
                scientific_name="Cicer arietinum",
                crop_type=CropType.LEGUME,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=300,
                drought_tolerance=4,
                irrigation_response=1.1,
                n_fixation_kg_ha=100,
                n_uptake_kg_ha=130,
                p_uptake_kg_ha=18,
                k_uptake_kg_ha=70,
                residue_cn_ratio=28,
                root_depth_cm=100,
                biomass_kg_ha=4500,
                soil_health_index=1,
                min_temp_c=5,
                max_temp_c=35,
                optimal_temp_c=24,
                frost_tolerance_c=-5,
                growing_degree_days=1000,
                pest_break_value=3,
                market_value_usd_ton=600,
                production_cost_usd_ha=400,
            ),
            CropCharacteristics(
                name="Lentil",
                scientific_name="Lens culinaris",
                crop_type=CropType.LEGUME,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=300,
                drought_tolerance=4,
                irrigation_response=1.1,
                n_fixation_kg_ha=80,
                n_uptake_kg_ha=110,
                p_uptake_kg_ha=15,
                k_uptake_kg_ha=60,
                residue_cn_ratio=22,
                root_depth_cm=60,
                biomass_kg_ha=3500,
                soil_health_index=1,
                min_temp_c=2,
                max_temp_c=30,
                optimal_temp_c=18,
                frost_tolerance_c=-6,
                growing_degree_days=950,
                pest_break_value=3,
                market_value_usd_ton=700,
                production_cost_usd_ha=350,
            ),



      
            CropCharacteristics(
                name="Canola",
                scientific_name="Brassica napus",
                crop_type=CropType.OILSEED,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=400,
                drought_tolerance=3,
                irrigation_response=1.2,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=180,
                p_uptake_kg_ha=35,
                k_uptake_kg_ha=150,
                residue_cn_ratio=40,
                root_depth_cm=100,
                biomass_kg_ha=8000,
                soil_health_index=0,
                min_temp_c=2,
                max_temp_c=30,
                optimal_temp_c=20,
                frost_tolerance_c=-8,
                growing_degree_days=1100,
                pest_break_value=2,
                disease_susceptibility={"sclerotinia": 3, "blackleg": 2},
                market_value_usd_ton=500,
                production_cost_usd_ha=550,
            ),
            CropCharacteristics(
                name="Sunflower",
                scientific_name="Helianthus annuus",
                crop_type=CropType.OILSEED,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=500,
                drought_tolerance=4,
                irrigation_response=1.1,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=120,
                p_uptake_kg_ha=25,
                k_uptake_kg_ha=180,
                residue_cn_ratio=35,
                root_depth_cm=150,
                biomass_kg_ha=9000,
                soil_health_index=0,
                min_temp_c=8,
                max_temp_c=38,
                optimal_temp_c=25,
                frost_tolerance_c=-2,
                growing_degree_days=1200,
                pest_break_value=2,
                market_value_usd_ton=400,
                production_cost_usd_ha=450,
            ),



  
            CropCharacteristics(
                name="Potato",
                scientific_name="Solanum tuberosum",
                crop_type=CropType.ROOT_TUBER,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=500,
                drought_tolerance=2,
                irrigation_response=1.4,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=150,
                p_uptake_kg_ha=40,
                k_uptake_kg_ha=250,
                residue_cn_ratio=30,
                root_depth_cm=60,
                biomass_kg_ha=6000,
                soil_health_index=-2,
                min_temp_c=7,
                max_temp_c=30,
                optimal_temp_c=18,
                frost_tolerance_c=-1,
                growing_degree_days=1000,
                pest_break_value=1,
                disease_susceptibility={"late_blight": 4, "potato_cyst": 3},
                market_value_usd_ton=250,
                production_cost_usd_ha=2500,
            ),




            CropCharacteristics(
                name="Winter Rye",
                scientific_name="Secale cereale",
                crop_type=CropType.COVER_CROP,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=300,
                drought_tolerance=4,
                irrigation_response=1.0,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=80,
                p_uptake_kg_ha=15,
                k_uptake_kg_ha=100,
                residue_cn_ratio=45,
                root_depth_cm=100,
                biomass_kg_ha=5000,
                soil_health_index=2,
                min_temp_c=-5,
                max_temp_c=25,
                optimal_temp_c=10,
                frost_tolerance_c=-20,
                growing_degree_days=600,
                pest_break_value=2,
                market_value_usd_ton=0,
                production_cost_usd_ha=100,
            ),
            CropCharacteristics(
                name="Hairy Vetch",
                scientific_name="Vicia villosa",
                crop_type=CropType.COVER_CROP,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=350,
                drought_tolerance=3,
                irrigation_response=1.0,
                n_fixation_kg_ha=120,
                n_uptake_kg_ha=150,
                p_uptake_kg_ha=20,
                k_uptake_kg_ha=80,
                residue_cn_ratio=15,
                root_depth_cm=80,
                biomass_kg_ha=4000,
                soil_health_index=2,
                min_temp_c=-5,
                max_temp_c=28,
                optimal_temp_c=15,
                frost_tolerance_c=-15,
                growing_degree_days=800,
                pest_break_value=2,
                market_value_usd_ton=0,
                production_cost_usd_ha=120,
            ),
            CropCharacteristics(
                name="Crimson Clover",
                scientific_name="Trifolium incarnatum",
                crop_type=CropType.COVER_CROP,
                growth_habit=GrowthHabit.ANNUAL,
                water_requirement_mm=400,
                drought_tolerance=2,
                irrigation_response=1.0,
                n_fixation_kg_ha=100,
                n_uptake_kg_ha=120,
                p_uptake_kg_ha=18,
                k_uptake_kg_ha=90,
                residue_cn_ratio=18,
                root_depth_cm=60,
                biomass_kg_ha=4500,
                soil_health_index=2,
                min_temp_c=0,
                max_temp_c=25,
                optimal_temp_c=15,
                frost_tolerance_c=-10,
                growing_degree_days=700,
                pest_break_value=2,
                market_value_usd_ton=0,
                production_cost_usd_ha=100,
            ),


      
            CropCharacteristics(
                name="Alfalfa",
                scientific_name="Medicago sativa",
                crop_type=CropType.FORAGE,
                growth_habit=GrowthHabit.PERENNIAL,
                water_requirement_mm=800,
                drought_tolerance=4,
                irrigation_response=1.3,
                n_fixation_kg_ha=250,
                n_uptake_kg_ha=300,
                p_uptake_kg_ha=40,
                k_uptake_kg_ha=250,
                residue_cn_ratio=20,
                root_depth_cm=200,
                biomass_kg_ha=15000,
                soil_health_index=2,
                min_temp_c=-10,
                max_temp_c=35,
                optimal_temp_c=22,
                frost_tolerance_c=-20,
                growing_degree_days=1500,
                pest_break_value=3,
                market_value_usd_ton=200,
                production_cost_usd_ha=400,
            ),
        ]

        for crop in default_crops:
            self.crop_database[crop.name.lower()] = crop
            logger.debug(f"Loaded crop: {crop.name}")

    def load_database(self, path: Path):
        """Load crop database from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            for crop_data in data:
                crop = CropCharacteristics(**crop_data)
                self.crop_database[crop.name.lower()] = crop
            logger.info(f"Loaded {len(data)} crops from {path}")
        except Exception as e:
            logger.error(f"Failed to load crop database: {e}")

    def save_database(self, path: Path):
        """Save crop database to JSON file."""
        try:
            data = [crop.model_dump() for crop in self.crop_database.values()]
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Saved {len(data)} crops to {path}")
        except Exception as e:
            logger.error(f"Failed to save crop database: {e}")

    def get_crop(self, name: str) -> Optional[CropCharacteristics]:
        """Get crop by name (case-insensitive)."""
        return self.crop_database.get(name.lower())

    def list_crops(self, crop_type: Optional[CropType] = None) -> List[CropCharacteristics]:
        """List all crops, optionally filtered by type."""
        crops = list(self.crop_database.values())
        if crop_type:
            crops = [c for c in crops if c.crop_type == crop_type]
        return sorted(crops, key=lambda c: c.name)

    def get_crops_by_type(self, crop_type: CropType) -> List[CropCharacteristics]:
        """Get all crops of a specific type."""
        return [c for c in self.crop_database.values() if c.crop_type == crop_type]

    def generate_rotations(
        self,
        location_id: str,
        years: int = 3,
        include_cover_crops: bool = True,
        include_legumes: bool = True,
        max_crops_per_year: int = 1,
    ) -> List[CropRotation]:
        """Generate candidate crop rotations."""
        rotations = []



    
        cereals = self.get_crops_by_type(CropType.CEREAL)
        legumes = self.get_crops_by_type(CropType.LEGUME) if include_legumes else []
        oilseeds = self.get_crops_by_type(CropType.OILSEED)
        cover_crops = self.get_crops_by_type(CropType.COVER_CROP) if include_cover_crops else []
        root_tubers = self.get_crops_by_type(CropType.ROOT_TUBER)
        forages = self.get_crops_by_type(CropType.FORAGE)


     
        rotation_patterns = []



        if cereals and legumes and years >= 3:
            for c1 in cereals[:2]:
                for l in legumes[:2]:
                    for c2 in cereals[:2]:
                        if c1 != c2 or years == 3:
                            rotation_patterns.append([c1, l, c2])


   
        if cereals and oilseeds and legumes and years >= 3:
            for c in cereals[:2]:
                for o in oilseeds[:1]:
                    for l in legumes[:2]:
                        rotation_patterns.append([c, o, l])



        if cereals and cover_crops and legumes and years >= 4:
            for c1 in cereals[:1]:
                for cc in cover_crops[:1]:
                    for c2 in cereals[:1]:
                        for l in legumes[:1]:
                            rotation_patterns.append([c1, cc, c2, l])



        if forages and years >= 4:
            for f in forages[:1]:

     
                for c in cereals[:1]:
                    rotation_patterns.append([f, f, f, c])



        if cereals and root_tubers and legumes and years >= 4:
            for c1 in cereals[:1]:
                for r in root_tubers[:1]:
                    for c2 in cereals[:1]:
                        for l in legumes[:1]:
                            rotation_patterns.append([c1, r, c2, l])



        for i, pattern in enumerate(rotation_patterns[:20]): 
            
            crops = []
            for j, char in enumerate(pattern[:years]):
                crop = Crop(characteristics=char)
                crops.append(crop)

            rotation = CropRotation(
                name=f"Rotation_{i+1}_{'-'.join(c.characteristics.name[:3] for c in crops)}",
                crops=crops,
                years=years,
                location_id=location_id,
            )
            rotations.append(rotation)

        return rotations

    def create_custom_rotation(
        self,
        name: str,
        crop_names: List[str],
        location_id: str,
    ) -> Optional[CropRotation]:
        """Create a rotation from a list of crop names."""
        crops = []
        for name in crop_names:
            char = self.get_crop(name)
            if not char:
                logger.warning(f"Unknown crop: {name}")
                return None
            crops.append(Crop(characteristics=char))

        if len(crops) < 2:
            logger.warning("Rotation must have at least 2 crops")
            return None

        return CropRotation(
            name=name,
            crops=crops,
            years=len(crops),
            location_id=location_id,
        )

    def add_crop(self, crop: CropCharacteristics):
        """Add a custom crop to the database."""
        self.crop_database[crop.name.lower()] = crop
        logger.info(f"Added crop: {crop.name}")

    def get_nitrogen_fixing_crops(self) -> List[CropCharacteristics]:
        """Get crops that fix nitrogen."""
        return [c for c in self.crop_database.values() if c.n_fixation_kg_ha > 0]

    def get_deep_rooted_crops(self, min_depth: int = 100) -> List[CropCharacteristics]:
        """Get crops with deep root systems."""
        return [c for c in self.crop_database.values() if c.root_depth_cm >= min_depth]

    def get_drought_tolerant_crops(self, min_tolerance: int = 4) -> List[CropCharacteristics]:
        """Get drought-tolerant crops."""
        return [c for c in self.crop_database.values() if c.drought_tolerance >= min_tolerance]