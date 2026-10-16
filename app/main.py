import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import logger
from app.core.database import init_db

from app.api.clients import router as clients_router
from app.api.campaigns import router as campaigns_router
from app.api.mailboxes import router as mailboxes_router
from app.api.analytics import router as analytics_router
from app.api.reports import router as reports_router
from app.api.webhooks import router as webhooks_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database
    logger.info("Initializing Smartlead Weekly Mailbox Analytics application...")
    init_db()
    logger.info("Application ready for on-demand reporting.")

    yield

    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Smartlead Weekly Mailbox Analytics",
    description="Mailbox-level email delivery and bounce rate analytics integration for Smartlead",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
from fastapi import Request
from app.clients.smartlead_exceptions import SmartleadAuthError, SmartleadRateLimitError, SmartleadApiError


@app.exception_handler(SmartleadAuthError)
async def smartlead_auth_exception_handler(request: Request, exc: SmartleadAuthError):
    logger.error(f"SmartleadAuthError handled: {exc.message}")
    return JSONResponse(
        status_code=401,
        content={
            "error": "Authentication Failed",
            "detail": "Smartlead API Authentication Failure (HTTP 401). Please check that your SMARTLEAD_API_KEY in the .env file is set to your actual Smartlead API key (currently it might still be 'your_api_key_here' or invalid).",
        },
    )


@app.exception_handler(SmartleadRateLimitError)
async def smartlead_ratelimit_exception_handler(request: Request, exc: SmartleadRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate Limit Exceeded", "detail": exc.message},
    )


@app.exception_handler(SmartleadApiError)
async def smartlead_api_exception_handler(request: Request, exc: SmartleadApiError):
    return JSONResponse(
        status_code=502,
        content={"error": "Smartlead API Error", "detail": exc.message},
    )

# Register API Routers
app.include_router(clients_router, prefix="/api")
app.include_router(campaigns_router, prefix="/api")
app.include_router(mailboxes_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "smartlead_api_configured": bool(settings.smartlead_api_key),
        "database_url": settings.database_url.split("://")[0] + "://***",
        "dry_run": settings.dry_run,
    }


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def dashboard():
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Smartlead Weekly Mailbox Analytics</h1><p>Dashboard template not found.</p>")
