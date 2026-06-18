from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.models.schemas import (
    BatchEvaluateResponse,
    EvaluateResponse,
    EvaluationMethod,
    JobStatus,
    JobStatusResponse,
)
from app.services.evaluator import Evaluator

router = APIRouter()


def _read_pdf(file: UploadFile, max_mb: int) -> None:
    allowed = ("application/pdf", "application/x-pdf", "application/octet-stream")
    if file.content_type and file.content_type not in allowed:
        raise HTTPException(400, "Resume must be a PDF")
    if file.filename and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Resume must be a PDF")
    if file.size and file.size > max_mb * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {max_mb}MB limit")


@router.get("/health")
async def health(request: Request):
    s = request.app.state.settings
    return {
        "status": "ok",
        "groq_configured": bool(s.groq_api_key),
        "model": s.groq_model,
        "default_mode": s.evaluation_mode,
        "langsmith_enabled": bool(s.langsmith_api_key),
    }


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    request: Request,
    job_description: str = Form(...),
    resume: UploadFile = File(...),
    mode: str = Form(None),
):
    settings = request.app.state.settings
    if not settings.groq_api_key:
        raise HTTPException(503, "GROQ_API_KEY not configured")
    if not job_description.strip():
        raise HTTPException(400, "Job description is required")

    _read_pdf(resume, settings.max_upload_mb)
    pdf_bytes = await resume.read()
    if not pdf_bytes or len(pdf_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(400, "Invalid or empty PDF")

    try:
        eval_mode = EvaluationMethod((mode or settings.evaluation_mode).lower())
    except ValueError:
        raise HTTPException(400, "Invalid mode. Use 'direct' or 'pipeline'.")

    queue = request.app.state.queue
    job = queue.create_job()
    evaluator = Evaluator(settings)

    async def run():
        job.result = await evaluator.evaluate_pdf(job_description, pdf_bytes, job.id, eval_mode)

    await queue.enqueue(job.id, run)
    return EvaluateResponse(job_id=job.id, status=JobStatus.queued)


@router.post("/evaluate/batch", response_model=BatchEvaluateResponse)
async def evaluate_batch(
    request: Request,
    job_description: str = Form(...),
    resumes: list[UploadFile] = File(...),
    mode: str = Form(None),
):
    settings = request.app.state.settings
    if not settings.groq_api_key:
        raise HTTPException(503, "GROQ_API_KEY not configured")
    if not job_description.strip():
        raise HTTPException(400, "Job description is required")
    if not resumes:
        raise HTTPException(400, "At least one resume is required")

    try:
        eval_mode = EvaluationMethod((mode or settings.evaluation_mode).lower())
    except ValueError:
        raise HTTPException(400, "Invalid mode. Use 'direct' or 'pipeline'.")

    queue = request.app.state.queue
    job_ids: list[str] = []
    evaluator = Evaluator(settings)

    for resume in resumes:
        _read_pdf(resume, settings.max_upload_mb)
        pdf_bytes = await resume.read()
        job = queue.create_job()
        job_ids.append(job.id)

        async def run(jd=job_description, pdf=pdf_bytes, j=job, m=eval_mode):
            j.result = await evaluator.evaluate_pdf(jd, pdf, j.id, m)

        await queue.enqueue(job.id, run)

    return BatchEvaluateResponse(job_ids=job_ids, queued=len(job_ids))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, request: Request):
    job = request.app.state.queue.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatusResponse(job_id=job.id, status=job.status, result=job.result, error=job.error)
