from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import configure_langsmith, get_settings
from app.core.queue import JobQueue
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings.cache_clear()
    settings = get_settings()
    configure_langsmith(settings)
    queue = JobQueue(concurrency=settings.worker_concurrency)
    await queue.start()
    app.state.queue = queue
    app.state.settings = settings
    yield
    await queue.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="AI Resume Screener", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    return app
