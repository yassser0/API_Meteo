"""
Point d'entrée principal de l'API Météo Synthétique.

Lance l'application FastAPI avec :
- Middleware de sécurité (CORS strict, headers HTTP)
- Initialisation du générateur et du store
- Planificateur de génération continue
- Endpoints REST documentés

AVERTISSEMENT : Toutes les données sont synthétiques et ne représentent
PAS les conditions météorologiques réelles.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.generator import SyntheticWeatherGenerator
from app.models import APIInfo, HealthStatus
from app.routers.weather import router as weather_router
from app.scheduler import WeatherScheduler
from app.storage import WeatherDataStore

# ---------------------------------------------------------------------------
# Configuration des logs
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# Timestamp de démarrage pour le calcul de l'uptime
_START_TIME = time.monotonic()


# ---------------------------------------------------------------------------
# Cycle de vie de l'application (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisation et nettoyage des ressources de l'application."""
    logger.info("=== Démarrage de l'API Météo Synthétique v%s ===", settings.APP_VERSION)
    logger.warning(
        "RAPPEL : Toutes les données générées sont SYNTHÉTIQUES et ne "
        "représentent PAS les conditions météorologiques réelles."
    )

    # Créer les composants principaux
    generator = SyntheticWeatherGenerator(
        anomaly_mode=settings.ANOMALY_MODE,
        anomaly_probability=settings.ANOMALY_PROBABILITY,
    )
    store = WeatherDataStore(max_records_per_city=settings.MAX_RECORDS_IN_MEMORY)
    scheduler = WeatherScheduler(
        generator=generator,
        store=store,
        interval_seconds=settings.SIMULATION_INTERVAL_SECONDS,
    )

    # Attacher au state de l'app pour accès dans les routes
    app.state.generator = generator
    app.state.store = store
    app.state.scheduler = scheduler

    # Générer un lot initial pour avoir des données dès le démarrage
    logger.info("Génération du lot initial de données synthétiques...")
    initial_measurements = generator.generate_batch(cities=settings.CITIES)
    store.add_batch(initial_measurements)
    logger.info("%d mesures initiales générées.", len(initial_measurements))

    # Démarrer le planificateur
    scheduler.start()

    yield

    # Shutdown : arrêter proprement le planificateur
    logger.info("Arrêt de l'API...")
    await scheduler.stop()
    logger.info("=== API Météo Synthétique arrêtée ===")


# ---------------------------------------------------------------------------
# Création de l'application FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware de sécurité
# ---------------------------------------------------------------------------

# CORS strict : uniquement les origines configurées (pas de wildcard *)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],  # Cette API est en lecture seule
    allow_headers=["Accept", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Ajoute les en-têtes de sécurité HTTP à chaque réponse."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    # Retirer l'en-tête Server pour éviter la divulgation de version
    # MutableHeaders ne supporte pas .pop(), utiliser del avec try/except
    try:
        del response.headers["server"]
    except KeyError:
        pass
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log les requêtes entrantes (sans données sensibles)."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    # Ne pas logger les query params complets pour éviter les fuites de données
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Gestionnaire d'erreurs global
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Gestionnaire d'erreurs global.
    Retourne un message générique sans exposer les détails internes.
    """
    logger.error(
        "Erreur non gérée sur %s %s : %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Une erreur interne s'est produite. Consultez les logs."},
    )


# ---------------------------------------------------------------------------
# Inclusion des routeurs
# ---------------------------------------------------------------------------

app.include_router(weather_router)


# ---------------------------------------------------------------------------
# Endpoints de base
# ---------------------------------------------------------------------------

@app.get(
    "/",
    response_model=APIInfo,
    summary="Informations sur l'API",
    tags=["info"],
)
async def root(request: Request):
    """Informations générales sur l'API Météo Synthétique."""
    return APIInfo(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        endpoints={
            "info": "GET /",
            "health": "GET /health",
            "latest": "GET /weather/latest",
            "current": "GET /weather/current",
            "history": "GET /weather/history",
            "generate": "GET /weather/generate",
            "export": "GET /weather/export",
            "docs": "GET /docs",
            "redoc": "GET /redoc",
        },
        cities=settings.CITIES,
        anomaly_mode_active=settings.ANOMALY_MODE,
    )


@app.get(
    "/health",
    response_model=HealthStatus,
    summary="État de l'API",
    tags=["info"],
)
async def health(request: Request):
    """Vérifie l'état de santé de l'API."""
    store: WeatherDataStore = request.app.state.store
    scheduler: WeatherScheduler = request.app.state.scheduler

    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(time.monotonic() - _START_TIME, 2),
        records_in_memory=store.get_total_count(),
        scheduler_running=scheduler.is_running,
        anomaly_mode=settings.ANOMALY_MODE,
        simulation_interval_seconds=scheduler.interval_seconds,
    )


# ---------------------------------------------------------------------------
# Point d'entrée CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
