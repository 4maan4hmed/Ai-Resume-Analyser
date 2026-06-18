import json

from langsmith import traceable

from app.config import Settings
from app.models.schemas import EvaluationMethod, EvaluationResult
from app.services.groq import GroqClient
from app.services.scoring import apply_scoring

DIRECT_PROMPT = """Expert technical recruiter. Score resume vs job description.

Score each component 0-100 only (no overall fit_score):
work_experience, projects, education, skills, certifications (null if none).

Each component: score, highlights, concerns, summary.
Include 3-6 strengths, 3-6 gaps. Qualitative reasoning only — no math.
Ignore protected attributes. Only score stated qualifications.

Return JSON:
{"strengths":[],"gaps":[],"reasoning":"","work_experience":{"score":0,"highlights":[],"concerns":[],"summary":""},
"projects":{...},"education":{...},"skills":{...},"certifications":{...}|null}"""


class Direct:
    def __init__(self, settings: Settings):
        self.groq = GroqClient(settings)

    @traceable(name="direct_evaluate")
    async def evaluate(self, job_description: str, resume_text: str, job_id: str | None = None) -> EvaluationResult:
        user = f"## Job Description\n{job_description}\n\n## Resume\n{resume_text}"
        parsed = json.loads(await self.groq.complete(DIRECT_PROMPT, user))
        parsed.setdefault("fit_score", 0)
        parsed.setdefault("recommendation", "weak_fit")
        result = EvaluationResult.model_validate(parsed)
        result.evaluation_method = EvaluationMethod.direct
        return apply_scoring(result)
