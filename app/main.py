from dotenv import load_dotenv

load_dotenv()  # must run before any SDK/OpenAI imports read env vars

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware # noqa: E402

from app.routers import chat, health  # noqa: E402
from app.vectore_store.store import get_vector_store  # noqa: E402
import logging  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the FAISS vector store on startup so the first request is fast."""
    import asyncio

    loop = asyncio.get_running_loop()
    logger.info("Pre-warming FAISS vector store...")
    await loop.run_in_executor(None, get_vector_store)
    logger.info("FAISS vector store ready.")
    yield


app = FastAPI(
    title="Multi-Agent AI Assistant",
    version="1.0.0",
    description="A FastAPI application powered by a multi-agent AI system using Ollama LLMs, RAG with FAISS vector search, real-time streaming via SSE, and persistent chat history backed by PostgreSQL.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
