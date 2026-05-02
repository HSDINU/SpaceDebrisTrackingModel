from __future__ import annotations

from dataclasses import dataclass

CORE_ONLY = "core_only"
CORE_PLUS_DISCOS = "core_plus_discos"
CORE_PLUS_DISCOS_PHYSICAL = "core_plus_discos_physical"

VALID_FEATURE_PROFILES = (
    CORE_ONLY,
    CORE_PLUS_DISCOS,
    CORE_PLUS_DISCOS_PHYSICAL,
)


DISCOS_NUMERIC_FROM_API = [
    "mass_kg",
    "length_m",
    "height_m",
    "depth_m",
    "diameter_m",
    "span_m",
    "x_sect_max_m2",
    "x_sect_min_m2",
    "x_sect_avg_m2",
    "destination_orbit_count",
    "dest_sma_m",
    "dest_inc_deg",
    "dest_ecc",
    "dest_raan_deg",
    "dest_arg_per_deg",
    "dest_mean_anomaly_deg",
]

DISCOS_PHYSICAL_SUBSET = [
    "mass_kg",
    "length_m",
    "height_m",
    "depth_m",
    "diameter_m",
    "span_m",
    "x_sect_max_m2",
    "x_sect_min_m2",
    "x_sect_avg_m2",
]


@dataclass(frozen=True)
class FeatureProfileSpec:
    profile: str
    discos_features: list[str]


def get_profile_spec(profile: str) -> FeatureProfileSpec:
    if profile == CORE_ONLY:
        return FeatureProfileSpec(profile=profile, discos_features=[])
    if profile == CORE_PLUS_DISCOS:
        return FeatureProfileSpec(profile=profile, discos_features=DISCOS_NUMERIC_FROM_API)
    if profile == CORE_PLUS_DISCOS_PHYSICAL:
        return FeatureProfileSpec(profile=profile, discos_features=DISCOS_PHYSICAL_SUBSET)
    raise ValueError(
        f"Geçersiz profile: {profile}. Geçerli: {', '.join(VALID_FEATURE_PROFILES)}"
    )


def normalize_profile(profile: str | None) -> str:
    p = (profile or CORE_ONLY).strip().lower()
    if p not in VALID_FEATURE_PROFILES:
        return CORE_ONLY
    return p
