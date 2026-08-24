from typing import Literal

from pydantic import BaseModel, ConfigDict


class AnalysisModel(BaseModel):
    """
    Base for every request model below.

    `extra="ignore"` matches the spec: a future `schema_version` may add
    fields, and we should log/process the ones we know rather than reject
    the whole request over ones we don't.
    """

    model_config = ConfigDict(extra="ignore")


class FeatureLocation(AnalysisModel):
    province: str | None
    district: str | None
    tambon: str | None


class AnalysisFeature(AnalysisModel):
    label: str | None
    geom_type: Literal["point", "line", "polygon"]
    buffer_m: float | None
    is_legal: bool
    length_m: float | None
    area_sqm: float | None
    location: FeatureLocation


class AnalysisProject(AnalysisModel):
    id: str
    name: str
    agency: str | None
    project_type: str
    project_sub_type: str
    default_buffer_m: float
    features: list[AnalysisFeature]
    created_at: str


class CategorySummary(AnalysisModel):
    category: str | None
    site_count: int
    guidance: str | None
    guidance_ref: str | None


class AnalysisSummary(AnalysisModel):
    total_sites: int
    total_geometries: int
    by_category: list[CategorySummary]


class SiteImpact(AnalysisModel):
    site_name: str | None
    category: str | None
    sub_category: str | None
    site_type: str | None
    site_type_path: list[str]
    province: str | None
    district: str | None
    tambon: str | None
    closest_distance_m: float
    overlap_area_sqm: float | None
    overlap_length_m: float | None
    overlap_percentage: float | None
    geometry_count: int
    provincial_heritage_be: str | None


class AnalysisRequest(AnalysisModel):
    schema_version: str
    project: AnalysisProject
    summary: AnalysisSummary
    sites: list[SiteImpact]
    sites_total: int
    sites_truncated: bool
