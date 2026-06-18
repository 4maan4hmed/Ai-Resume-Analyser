from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# --- API enums & job models ---

class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Recommendation(str, Enum):
    strong_fit = "strong_fit"
    moderate_fit = "moderate_fit"
    weak_fit = "weak_fit"
    not_a_fit = "not_a_fit"


class EvaluationMethod(str, Enum):
    direct = "direct"
    pipeline = "pipeline"


# --- Extraction models (pipeline step 1 & 2) ---

def _flatten(items: Any) -> list[str]:
    if items is None:
        return []
    if not items:
        return []
    if not isinstance(items, list):
        items = [items]
    out: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            parts = [
                item.get("degree") or item.get("qualification"),
                item.get("institution") or item.get("school") or item.get("university"),
                item.get("field") or item.get("major") or item.get("specialization"),
                item.get("year") or item.get("duration"),
            ]
            text = ", ".join(str(p).strip() for p in parts if p)
            out.append(text or str(item))
    return out


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, dict):
        return ", ".join(str(v) for v in value.values() if v) or default
    return str(value).strip() or default


class JobRequirements(BaseModel):
    role_title: str = ""
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    min_years_experience: float | None = None
    education_requirements: list[str] | None = None
    required_certifications: list[str] | None = None
    responsibilities: list[str] | None = None
    keywords: list[str] | None = None

    @field_validator(
        "required_skills", "preferred_skills", "responsibilities",
        "keywords", "education_requirements", "required_certifications", mode="before",
    )
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        return _flatten(v)

    @field_validator("role_title", mode="before")
    @classmethod
    def _title(cls, v: Any) -> str:
        return _str(v)

    @model_validator(mode="after")
    def _defaults(self) -> "JobRequirements":
        for name in (
            "required_skills", "preferred_skills", "education_requirements",
            "required_certifications", "responsibilities", "keywords",
        ):
            if getattr(self, name) is None:
                setattr(self, name, [])
        return self


class WorkExperienceItem(BaseModel):
    title: str = "Unknown"
    company: str = ""
    duration: str = ""
    highlights: list[str] | None = None

    @field_validator("title", "company", "duration", mode="before")
    @classmethod
    def _fields(cls, v: Any) -> str:
        return _str(v)

    @field_validator("title", mode="after")
    @classmethod
    def _title(cls, v: str) -> str:
        return v or "Unknown"

    @field_validator("highlights", mode="before")
    @classmethod
    def _highlights(cls, v: Any) -> list[str]:
        return _flatten(v)

    @model_validator(mode="after")
    def _defaults(self) -> "WorkExperienceItem":
        if self.highlights is None:
            self.highlights = []
        return self


class ProjectItem(BaseModel):
    name: str = "Unnamed project"
    technologies: list[str] | None = None
    description: str = ""
    @classmethod
    def _fields(cls, v: Any) -> str:
        return _str(v)

    @field_validator("name", mode="after")
    @classmethod
    def _name(cls, v: str) -> str:
        return v or "Unnamed project"

    @field_validator("technologies", mode="before")
    @classmethod
    def _techs(cls, v: Any) -> list[str]:
        return _flatten(v)

    @model_validator(mode="after")
    def _defaults(self) -> "ProjectItem":
        if self.technologies is None:
            self.technologies = []
        return self


class ResumeProfile(BaseModel):
    skills: list[str] | None = None
    work_experience: list[WorkExperienceItem] | None = None
    projects: list[ProjectItem] | None = None
    education: list[str] | None = None
    certifications: list[str] | None = None
    total_years_experience: float | None = None

    @field_validator("skills", "education", "certifications", mode="before")
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        return _flatten(v)

    @field_validator("work_experience", mode="before")
    @classmethod
    def _jobs(cls, v: Any) -> list:
        if v is None:
            return []
        if not v:
            return []
        items = v if isinstance(v, list) else [v]
        return [i if isinstance(i, dict) else {"title": _str(i)} for i in items]

    @field_validator("projects", mode="before")
    @classmethod
    def _projects(cls, v: Any) -> list:
        if v is None:
            return []
        if not v:
            return []
        items = v if isinstance(v, list) else [v]
        return [i if isinstance(i, dict) else {"name": _str(i)} for i in items]

    @model_validator(mode="after")
    def _defaults(self) -> "ResumeProfile":
        if self.skills is None:
            self.skills = []
        if self.work_experience is None:
            self.work_experience = []
        if self.projects is None:
            self.projects = []
        if self.education is None:
            self.education = []
        if self.certifications is None:
            self.certifications = []
        return self


# --- Evaluation models ---

class ComponentEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    highlights: list[str] | None = None
    concerns: list[str] | None = None
    summary: str = ""

    @field_validator("highlights", "concerns", mode="before")
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        return _flatten(v)

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, v: Any) -> str:
        return _str(v)

    @model_validator(mode="after")
    def _defaults(self) -> "ComponentEvaluation":
        if self.highlights is None:
            self.highlights = []
        if self.concerns is None:
            self.concerns = []
        return self


class ScoreBreakdown(BaseModel):
    component: str
    weight: float
    raw_score: float
    weighted_score: float
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    details: str = ""


class RawFitComparison(BaseModel):
    strengths: list[str] | None = None
    gaps: list[str] | None = None
    reasoning: str = ""
    work_experience: ComponentEvaluation
    projects: ComponentEvaluation
    education: ComponentEvaluation
    skills: ComponentEvaluation
    certifications: ComponentEvaluation | None = None

    @field_validator("strengths", "gaps", mode="before")
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        return _flatten(v)

    @model_validator(mode="after")
    def _defaults(self) -> "RawFitComparison":
        if self.strengths is None:
            self.strengths = []
        if self.gaps is None:
            self.gaps = []
        return self


class EvaluationResult(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    recommendation: Recommendation
    strengths: list[str]
    gaps: list[str]
    reasoning: str
    work_experience: ComponentEvaluation
    projects: ComponentEvaluation
    education: ComponentEvaluation
    skills: ComponentEvaluation
    certifications: ComponentEvaluation | None = None
    score_breakdown: list[ScoreBreakdown] = Field(default_factory=list)
    jd_extraction: JobRequirements | None = None
    resume_extraction: ResumeProfile | None = None
    evaluation_method: EvaluationMethod = EvaluationMethod.direct


class EvaluateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: Optional[EvaluationResult] = None
    error: Optional[str] = None


class BatchEvaluateResponse(BaseModel):
    job_ids: list[str]
    queued: int
