from app.models.schemas import (
    ComponentEvaluation,
    EvaluationResult,
    RawFitComparison,
    Recommendation,
    ScoreBreakdown,
)

WEIGHTS = {
    "skills": 0.35,
    "work_experience": 0.30,
    "projects": 0.15,
    "education": 0.10,
    "certifications": 0.10,
}


def _recommendation(score: int) -> Recommendation:
    if score >= 80:
        return Recommendation.strong_fit
    if score >= 60:
        return Recommendation.moderate_fit
    if score >= 40:
        return Recommendation.weak_fit
    return Recommendation.not_a_fit


def _components(result: EvaluationResult | RawFitComparison) -> list[ComponentEvaluation]:
    comps = [result.skills, result.work_experience, result.projects, result.education]
    if result.certifications:
        comps.append(result.certifications)
    return comps


def compute_score(
    skills: ComponentEvaluation,
    work_experience: ComponentEvaluation,
    projects: ComponentEvaluation,
    education: ComponentEvaluation,
    certifications: ComponentEvaluation | None,
) -> tuple[int, list[ScoreBreakdown], Recommendation]:
    weights = dict(WEIGHTS)
    named = {
        "skills": skills,
        "work_experience": work_experience,
        "projects": projects,
        "education": education,
    }
    if certifications:
        named["certifications"] = certifications
    else:
        weights["skills"] += weights.pop("certifications")

    breakdown: list[ScoreBreakdown] = []
    total = 0.0
    for name, comp in named.items():
        w = weights[name]
        weighted = round(comp.score * w, 1)
        total += weighted
        breakdown.append(ScoreBreakdown(
            component=name,
            weight=w,
            raw_score=comp.score,
            weighted_score=weighted,
            matched=comp.highlights[:5],
            missing=comp.concerns[:5],
            details=f"{comp.score}/100 × {int(w * 100)}% = {weighted}",
        ))

    fit_score = max(0, min(100, round(total)))
    return fit_score, breakdown, _recommendation(fit_score)


def _formula(breakdown: list[ScoreBreakdown], fit_score: int) -> str:
    parts = [f"{b.component}({b.raw_score}×{b.weight})" for b in breakdown]
    return f"Weighted score: {' + '.join(parts)} = {fit_score}/100"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        t = item.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def enrich_result(result: EvaluationResult) -> EvaluationResult:
    if not result.strengths or not result.gaps:
        comps = _components(result)
        strengths = _unique([h for c in comps for h in c.highlights] + [m for b in result.score_breakdown for m in b.matched])
        gaps = _unique([c for comp in comps for c in comp.concerns] + [m for b in result.score_breakdown for m in b.missing])
        if not result.strengths:
            result.strengths = strengths[:8] or ["No major strengths identified"]
        if not result.gaps:
            result.gaps = gaps[:8] or ["No major gaps identified"]
    return result


def apply_scoring(result: EvaluationResult) -> EvaluationResult:
    fit_score, breakdown, rec = compute_score(
        result.skills, result.work_experience, result.projects,
        result.education, result.certifications,
    )
    formula = _formula(breakdown, fit_score)
    result.fit_score = fit_score
    result.recommendation = rec
    result.score_breakdown = breakdown
    if formula not in result.reasoning:
        result.reasoning = f"{formula}. {result.reasoning}".strip()
    return enrich_result(result)


def from_raw_comparison(raw: RawFitComparison) -> EvaluationResult:
    fit_score, breakdown, rec = compute_score(
        raw.skills, raw.work_experience, raw.projects,
        raw.education, raw.certifications,
    )
    formula = _formula(breakdown, fit_score)
    return enrich_result(EvaluationResult(
        fit_score=fit_score,
        recommendation=rec,
        strengths=raw.strengths,
        gaps=raw.gaps,
        reasoning=f"{formula}. {raw.reasoning}".strip(),
        work_experience=raw.work_experience,
        projects=raw.projects,
        education=raw.education,
        skills=raw.skills,
        certifications=raw.certifications,
        score_breakdown=breakdown,
    ))
