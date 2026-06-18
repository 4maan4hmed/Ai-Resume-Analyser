from app.config import Settings
from app.models.schemas import EvaluationMethod, EvaluationResult
from app.services.direct import Direct
from app.services.pdf import extract_text
from app.services.pipeline import Pipeline


class Evaluator:
    def __init__(self, settings: Settings):
        self.direct = Direct(settings)
        self.pipeline = Pipeline(settings)

    async def evaluate_pdf(
        self,
        job_description: str,
        resume_pdf: bytes,
        job_id: str | None = None,
        mode: EvaluationMethod = EvaluationMethod.direct,
    ) -> EvaluationResult:
        text = extract_text(resume_pdf)
        if mode == EvaluationMethod.pipeline:
            return await self.pipeline.evaluate(job_description, text, job_id)
        return await self.direct.evaluate(job_description, text, job_id)
