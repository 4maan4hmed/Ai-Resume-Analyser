import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from app.models.schemas import EvaluationResult, JobStatus


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.queued
    result: Optional[EvaluationResult] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobQueue:
    def __init__(self, concurrency: int = 4):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._jobs: dict[str, Job] = {}
        self._handlers: dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}
        self._concurrency = concurrency
        self._workers: list[asyncio.Task] = []
        self._running = False

    def create_job(self) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(id=job_id)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    async def enqueue(
        self,
        job_id: str,
        handler: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._handlers[job_id] = handler
        await self._queue.put(job_id)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for _ in range(self._concurrency):
            self._workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        self._running = False
        for _ in self._workers:
            await self._queue.put("")
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def _worker(self) -> None:
        while self._running:
            job_id = await self._queue.get()
            if not job_id:
                break
            job = self._jobs.get(job_id)
            handler = self._handlers.pop(job_id, None)
            if not job or not handler:
                self._queue.task_done()
                continue
            job.status = JobStatus.processing
            try:
                await handler()
                if job.status == JobStatus.processing:
                    job.status = JobStatus.completed
            except Exception as exc:
                job.status = JobStatus.failed
                job.error = str(exc)
            finally:
                self._queue.task_done()
