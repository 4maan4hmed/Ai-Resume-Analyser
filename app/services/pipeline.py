import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langsmith import traceable

from app.config import Settings
from app.models.schemas import EvaluationMethod, EvaluationResult, JobRequirements, RawFitComparison, ResumeProfile
from app.services.scoring import from_raw_comparison


class Pipeline:
    def __init__(self, settings: Settings):
        llm = ChatGroq(groq_api_key=settings.groq_api_key, model_name=settings.groq_model, temperature=0.1)
        structured = lambda model: llm.with_structured_output(model, method="json_mode")
        self._extract_jd = (
            ChatPromptTemplate.from_messages([
                ("system", "Extract hiring requirements. Use [] for empty lists, never null. Only explicit information."),
                ("human", "{text}"),
            ])
            | structured(JobRequirements)
        )
        self._extract_resume = (
            ChatPromptTemplate.from_messages([
                ("system", "Extract resume facts. Use [] for empty lists, never null. Do not invent experience."),
                ("human", "{text}"),
            ])
            | structured(ResumeProfile)
        )
        self._compare = (
            ChatPromptTemplate.from_messages([(
                "system",
                """Compare job requirements vs resume profile. Score each component 0-100 only (no overall score):
skills, work_experience, projects, education, certifications (omit if N/A).
Use [] for empty lists. Include 3-6 strengths, 3-6 gaps, qualitative reasoning. Ignore protected attributes.""",
            ), ("human", "Job Requirements:\n{jd}\n\nResume Profile:\n{resume}")])
            | structured(RawFitComparison)
        )

    def _cfg(self, job_id: str | None, step: str) -> RunnableConfig:
        return RunnableConfig(run_name=step, metadata={"job_id": job_id or "unknown", "step": step})

    @traceable(name="pipeline_evaluate")
    async def evaluate(self, job_description: str, resume_text: str, job_id: str | None = None) -> EvaluationResult:
        jd = await self._extract_jd.ainvoke({"text": job_description}, config=self._cfg(job_id, "1_extract_jd"))
        resume = await self._extract_resume.ainvoke({"text": resume_text}, config=self._cfg(job_id, "2_extract_resume"))
        raw = await self._compare.ainvoke(
            {"jd": json.dumps(jd.model_dump(), indent=2), "resume": json.dumps(resume.model_dump(), indent=2)},
            config=self._cfg(job_id, "3_compare"),
        )
        result = from_raw_comparison(raw)
        result.jd_extraction = jd
        result.resume_extraction = resume
        result.evaluation_method = EvaluationMethod.pipeline
        return result
