from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.classifier import ModelInferenceError
from app.config import get_settings
from app.news import NewsProviderError
from app.schemas import AnalyzeRequest, AnalyzeResponse, StockItem
from app.service import SentimentService
from app.stocks import list_stocks

settings = get_settings()
service = SentimentService(settings)

app = FastAPI(
    title="StockQ Financial News Sentiment API",
    version="1.0.0",
    description="Provider-backed financial news retrieval and FinBERT sentiment analysis.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(NewsProviderError)
async def provider_error_handler(_request: Request, exc: NewsProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": "news_provider_error", "message": str(exc)}},
    )


@app.exception_handler(ModelInferenceError)
async def model_error_handler(_request: Request, exc: ModelInferenceError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": "model_inference_error", "message": str(exc)}},
    )


@app.exception_handler(ValueError)
async def request_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": "invalid_request", "message": str(exc)}},
    )


@app.get("/api/v1/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "news_provider": settings.news_provider,
        "news_configured": settings.news_available,
        "model": settings.finbert_model,
        "model_status": getattr(service.classifier, "status", "unknown"),
        "demo_mode_available": settings.demo_mode_available,
    }


@app.get("/api/v1/stocks", response_model=list[StockItem])
async def stocks() -> list[StockItem]:
    return list_stocks()


@app.get("/api/v1/sentiment/sources")
async def sources() -> dict[str, object]:
    return {
        "providers": [{
            "name": settings.news_provider_display_name,
            "configured": settings.news_available,
            "availability": (
                "configured"
                if settings.news_available
                else f"{'GNEWS_API_KEY' if settings.news_provider.casefold() == 'gnews' else 'NEWS_API_KEY'} required"
            ),
            "supports_demo_fixtures": settings.demo_mode_available,
            "cache_ttl_seconds": settings.news_cache_ttl_seconds,
        }],
        "model": settings.finbert_model,
        "model_status": getattr(service.classifier, "status", "unknown"),
        "model_loaded_on_demand": True,
        "demo_mode_available": settings.demo_mode_available,
        "max_age_days": settings.provider_max_age_days,
    }


@app.post("/api/v1/sentiment/analyze", response_model=AnalyzeResponse)
async def analyze_sentiment(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        if request.demo_mode and not settings.demo_mode_available:
            raise HTTPException(
                status_code=403,
                detail={"code": "demo_mode_disabled", "message": "Demo mode is disabled. Configure ENABLE_DEMO_MODE=true only in a development or test environment."},
            )
        return await service.analyze(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_request", "message": str(exc)},
        ) from exc


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "StockQ Financial News Sentiment API", "docs": "/docs"}
