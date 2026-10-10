"""Tests for data models."""
import pytest
from datetime import date

from src.models.location import Location
from src.models.soil import SoilProfile, SoilLayer, SoilTexture
from src.models.crop import (
    Crop,
    CropCharacteristics,
    CropRotation,
    CropType,
    GrowthHabit,
)
from src.models.climate import ClimateData, ClimateSummary, ClimateVariable
from src.models.recommendation import (
    RotationRecommendation,
    RecommendationScore,
    Priority,
    RotationComparison,
)


class TestLocation:
    def test_valid_location(self):
        loc = Location(latitude=40.7128, longitude=-74.0060, name="New York")
        assert loc.latitude == 40.7128
        assert loc.longitude == -74.0060
        assert loc.name == "New York"

    def test_invalid_latitude(self):
        with pytest.raises(ValueError):
            Location(latitude=91, longitude=0)

    def test_invalid_longitude(self):
        with pytest.raises(ValueError):
            Location(latitude=0, longitude=181)

    def test_tuple_conversion(self):
        loc = Location(latitude=40.7128, longitude=-74.0060)
        assert loc.to_tuple() == (40.7128, -74.0060)


class TestSoilLayer:
    def test_valid_layer(self):
        layer = SoilLayer(
            depth_top=0,
            depth_bottom=20,
            texture=SoilTexture.LOAM,
            organic_carbon=2.5,
            ph=6.5,
        )
        assert layer.thickness == 20
        assert layer.texture == SoilTexture.LOAM

    def test_invalid_depth_order(self):
        with pytest.raises(ValueError):
            SoilLayer(depth_top=20, depth_bottom=10, texture=SoilTexture.LOAM)


class TestSoilProfile:
    def test_profile_creation(self):
        layers = [
            SoilLayer(depth_top=0, depth_bottom=20, texture=SoilTexture.LOAM, organic_carbon=2.5, ph=6.5, bulk_density=1.35),
            SoilLayer(depth_top=20, depth_bottom=50, texture=SoilTexture.CLAY_LOAM, organic_carbon=1.0, ph=6.8, bulk_density=1.45),
        ]
        profile = SoilProfile(location_id="test", layers=layers)
        assert profile.max_depth == 50
        assert len(profile.layers) == 2

    def test_total_organic_carbon(self):
        layers = [
            SoilLayer(depth_top=0, depth_bottom=20, texture=SoilTexture.LOAM, organic_carbon=2.5, ph=6.5, bulk_density=1.35),
            SoilLayer(depth_top=20, depth_bottom=50, texture=SoilTexture.CLAY_LOAM, organic_carbon=1.0, ph=6.8, bulk_density=1.45),
        ]
        profile = SoilProfile(location_id="test", layers=layers)
        # SOC = sum(OC% * BD * thickness * 10)
        # Layer 1: 2.5 * 1.35 * 20 * 10 = 675
        # Layer 2: 1.0 * 1.45 * 30 * 10 = 435
        # Total = 1110 kg/ha = 11.1 t/ha
        assert profile.total_organic_carbon == 11.1

    def test_average_ph(self):
        layers = [
            SoilLayer(depth_top=0, depth_bottom=20, texture=SoilTexture.LOAM, ph=6.0),
            SoilLayer(depth_top=20, depth_bottom=50, texture=SoilTexture.CLAY_LOAM, ph=7.0),
        ]
        profile = SoilProfile(location_id="test", layers=layers)
        # Weighted average: (6.0*20 + 7.0*30) / 50 = 6.6
        assert profile.average_ph == 6.6

    def test_get_layer_at_depth(self):
        layers = [
            SoilLayer(depth_top=0, depth_bottom=20, texture=SoilTexture.LOAM),
            SoilLayer(depth_top=20, depth_bottom=50, texture=SoilTexture.CLAY_LOAM),
        ]
        profile = SoilProfile(location_id="test", layers=layers)
        layer = profile.get_layer_at_depth(10)
        assert layer is not None
        assert layer.depth_top == 0

        layer = profile.get_layer_at_depth(30)
        assert layer is not None
        assert layer.depth_top == 20

        layer = profile.get_layer_at_depth(60)
        assert layer is None


class TestCropCharacteristics:
    def test_valid_crop(self):
        crop = CropCharacteristics(
            name="Test Crop",
            crop_type=CropType.CEREAL,
            water_requirement_mm=500,
            drought_tolerance=3,
            n_fixation_kg_ha=0,
            n_uptake_kg_ha=150,
            p_uptake_kg_ha=30,
            k_uptake_kg_ha=120,
            residue_cn_ratio=50,
            root_depth_cm=100,
            biomass_kg_ha=10000,
            min_temp_c=10,
            max_temp_c=35,
            optimal_temp_c=25,
            growing_degree_days=1200,
        )
        assert crop.name == "Test Crop"
        assert crop.crop_type == CropType.CEREAL

    def test_invalid_temp_range(self):
        with pytest.raises(ValueError):
            CropCharacteristics(
                name="Test",
                crop_type=CropType.CEREAL,
                water_requirement_mm=500,
                drought_tolerance=3,
                n_fixation_kg_ha=0,
                n_uptake_kg_ha=150,
                p_uptake_kg_ha=30,
                k_uptake_kg_ha=120,
                residue_cn_ratio=50,
                root_depth_cm=100,
                biomass_kg_ha=10000,
                min_temp_c=30,
                max_temp_c=20,  # Invalid: max < min
                optimal_temp_c=25,
                growing_degree_days=1200,
            )


class TestCropRotation:
    def test_rotation_creation(self):
        crop1 = Crop(characteristics=CropCharacteristics(
            name="Wheat", crop_type=CropType.CEREAL, water_requirement_mm=450,
            drought_tolerance=3, n_fixation_kg_ha=0, n_uptake_kg_ha=150,
            p_uptake_kg_ha=30, k_uptake_kg_ha=120, residue_cn_ratio=80,
            root_depth_cm=120, biomass_kg_ha=10000, min_temp_c=3, max_temp_c=32,
            optimal_temp_c=20, growing_degree_days=1100
        ))
        crop2 = Crop(characteristics=CropCharacteristics(
            name="Soybean", crop_type=CropType.LEGUME, water_requirement_mm=450,
            drought_tolerance=3, n_fixation_kg_ha=150, n_uptake_kg_ha=200,
            p_uptake_kg_ha=25, k_uptake_kg_ha=100, residue_cn_ratio=30,
            root_depth_cm=80, biomass_kg_ha=6000, min_temp_c=10, max_temp_c=35,
            optimal_temp_c=26, growing_degree_days=1200
        ))

        rotation = CropRotation(name="Test Rotation", crops=[crop1, crop2], years=2, location_id="test")
        assert rotation.years == 2
        assert rotation.has_legume is True
        assert rotation.has_cover_crop is False
        assert rotation.total_nitrogen_balance == 50  # 150 - 150 + 150 - 200 = -50? Wait: wheat n_balance = 0-150=-150, soybean = 150-200=-50. Total = -200
        # Let me recalculate: wheat: 0 - 150 = -150, soybean: 150 - 200 = -50, total = -200
        assert rotation.total_nitrogen_balance == -200

    def test_diversity_index(self):
        crop1 = Crop(characteristics=CropCharacteristics(
            name="Wheat", crop_type=CropType.CEREAL, water_requirement_mm=450,
            drought_tolerance=3, n_fixation_kg_ha=0, n_uptake_kg_ha=150,
            p_uptake_kg_ha=30, k_uptake_kg_ha=120, residue_cn_ratio=80,
            root_depth_cm=120, biomass_kg_ha=10000, min_temp_c=3, max_temp_c=32,
            optimal_temp_c=20, growing_degree_days=1100
        ))
        crop2 = Crop(characteristics=CropCharacteristics(
            name="Soybean", crop_type=CropType.LEGUME, water_requirement_mm=450,
            drought_tolerance=3, n_fixation_kg_ha=150, n_uptake_kg_ha=200,
            p_uptake_kg_ha=25, k_uptake_kg_ha=100, residue_cn_ratio=30,
            root_depth_cm=80, biomass_kg_ha=6000, min_temp_c=10, max_temp_c=35,
            optimal_temp_c=26, growing_degree_days=1200
        ))
        crop3 = Crop(characteristics=CropCharacteristics(
            name="Canola", crop_type=CropType.OILSEED, water_requirement_mm=400,
            drought_tolerance=3, n_fixation_kg_ha=0, n_uptake_kg_ha=180,
            p_uptake_kg_ha=35, k_uptake_kg_ha=150, residue_cn_ratio=40,
            root_depth_cm=100, biomass_kg_ha=8000, min_temp_c=2, max_temp_c=30,
            optimal_temp_c=20, growing_degree_days=1100
        ))

        # 3 different crop types = higher diversity
        rotation = CropRotation(name="Diverse", crops=[crop1, crop2, crop3], years=3, location_id="test")
        diversity = rotation.diversity_index()
        # Shannon index for 3 equally represented types: -3*(1/3)*ln(1/3) = ln(3) ≈ 1.099
        assert diversity > 1.0

        # 2 types
        rotation2 = CropRotation(name="Less Diverse", crops=[crop1, crop2], years=2, location_id="test")
        diversity2 = rotation2.diversity_index()
        # -2*(1/2)*ln(1/2) = ln(2) ≈ 0.693
        assert diversity2 < diversity


class TestClimateData:
    def test_vapor_pressure_deficit(self):
        data = ClimateData(
            location_id="test",
            date=date(2024, 6, 15),
            temperature_2m_mean=25.0,
            relative_humidity=60.0,
        )
        vpd = data.vapor_pressure_deficit
        assert vpd is not None
        # At 25°C, es ≈ 3.17 kPa, VPD = 3.17 * (1 - 0.6) = 1.27 kPa
        assert 1.2 < vpd < 1.4


class TestClimateSummary:
    def test_aridity_index(self):
        summary = ClimateSummary(
            location_id="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            total_precipitation=800,
            total_pet=1200,
        )
        assert summary.aridity_index == 1.5  # 1200/800


class TestRecommendationModels:
    def test_priority_score(self):
        score = RecommendationScore(
            rotation_id="rot1",
            priority=Priority.YIELD,
            score=85.5,
            rank=1,
        )
        assert score.priority == Priority.YIELD
        assert score.score == 85.5
        assert score.rank == 1

    def test_rotation_recommendation(self):
        crop = Crop(characteristics=CropCharacteristics(
            name="Wheat", crop_type=CropType.CEREAL, water_requirement_mm=450,
            drought_tolerance=3, n_fixation_kg_ha=0, n_uptake_kg_ha=150,
            p_uptake_kg_ha=30, k_uptake_kg_ha=120, residue_cn_ratio=80,
            root_depth_cm=120, biomass_kg_ha=10000, min_temp_c=3, max_temp_c=32,
            optimal_temp_c=20, growing_degree_days=1100
        ))
        rotation = CropRotation(name="Test", crops=[crop], years=1, location_id="test")

        rec = RotationRecommendation(
            rotation=rotation,
            overall_score=80.0,
            priority_scores=[
                RecommendationScore(rotation_id="test", priority=Priority.YIELD, score=85.0),
                RecommendationScore(rotation_id="test", priority=Priority.SOIL_HEALTH, score=75.0),
            ],
            generated_at="2024-01-01T00:00:00Z",
        )
        assert rec.overall_score == 80.0
        assert rec.get_score(Priority.YIELD) == 85.0
        assert rec.get_score(Priority.WATER_CONSERVATION) is None

    def test_rotation_comparison(self):
        crop = Crop(characteristics=CropCharacteristics(
            name="Wheat", crop_type=CropType.CEREAL, water_requirement_mm=450,
            drought_tolerance=3, n_fixation_kg_ha=0, n_uptake_kg_ha=150,
            p_uptake_kg_ha=30, k_uptake_kg_ha=120, residue_cn_ratio=80,
            root_depth_cm=120, biomass_kg_ha=10000, min_temp_c=3, max_temp_c=32,
            optimal_temp_c=20, growing_degree_days=1100
        ))

        rec1 = RotationRecommendation(
            rotation=CropRotation(name="Rot1", crops=[crop], years=1, location_id="test"),
            overall_score=80.0,
            priority_scores=[RecommendationScore(rotation_id="r1", priority=Priority.YIELD, score=85.0)],
            generated_at="2024-01-01T00:00:00Z",
        )
        rec2 = RotationRecommendation(
            rotation=CropRotation(name="Rot2", crops=[crop], years=1, location_id="test"),
            overall_score=70.0,
            priority_scores=[RecommendationScore(rotation_id="r2", priority=Priority.YIELD, score=75.0)],
            generated_at="2024-01-01T00:00:00Z",
        )

        comparison = RotationComparison(
            location_id="test",
            recommendations=[rec1, rec2],
        )

        assert comparison.best_overall == rec1
        assert comparison.best_by_priority[Priority.YIELD] == rec1

        table = comparison.summary_table()
        assert len(table) == 2
        assert table[0]["overall_score"] == 80.0  # Sorted descending