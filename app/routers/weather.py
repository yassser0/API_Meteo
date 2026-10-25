"""
Routeur FastAPI pour les endpoints météorologiques.

AVERTISSEMENT : Toutes les données retournées sont entièrement synthétiques
et ne représentent pas les conditions météorologiques réelles.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.generator import SyntheticWeatherGenerator
from app.models import WeatherBatch, WeatherMeasurement
from app.storage import WeatherDataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/weather", tags=["weather"])

SYNTHETIC_WARNING = (
    "DONNÉES SYNTHÉTIQUES : Ces données météorologiques sont entièrement "
    "générées par simulation et ne représentent PAS les conditions "
    "météorologiques réelles."
)


# ---------------------------------------------------------------------------
# Helpers de validation des paramètres (éviter l'injection via query params)
# ---------------------------------------------------------------------------

def _validate_city(city: Optional[str]) -> Optional[str]:
    """Valide et sanitize le paramètre ville."""
    if city is None:
        return None
    import re
    cleaned = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s\-]", "", city).strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Paramètre 'city' invalide.")
    if len(cleaned) > 100:
        raise HTTPException(status_code=400, detail="Paramètre 'city' trop long (max 100 caractères).")
    return cleaned


def _validate_iso_timestamp(ts: Optional[str], param_name: str) -> Optional[str]:
    """Valide qu'un timestamp est au format ISO 8601."""
    if ts is None:
        return None
    import re
    # Pattern ISO 8601 simplifié
    pattern = r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?$"
    if not re.match(pattern, ts):
        raise HTTPException(
            status_code=400,
            detail=f"Paramètre '{param_name}' doit être au format ISO 8601 (ex: 2024-01-15T14:30:00Z).",
        )
    return ts


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/latest",
    response_model=dict,
    summary="Dernière mesure par ville",
    description=(
        "Retourne la dernière mesure synthétique disponible pour chaque ville simulée. "
        + SYNTHETIC_WARNING
    ),
)
async def get_latest(
    request: Request,
    city: Annotated[Optional[str], Query(description="Filtrer par ville")] = None,
):
    """Retourne la dernière mesure synthétique disponible par ville."""
    store: WeatherDataStore = request.app.state.store
    validated_city = _validate_city(city)

    measurements = store.get_latest(city=validated_city)

    if validated_city and not measurements:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune donnée disponible pour la ville '{validated_city}'.",
        )

    return {
        "warning": SYNTHETIC_WARNING,
        "count": len(measurements),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "measurements": [m.model_dump() for m in measurements],
    }


@router.get(
    "/current",
    response_model=dict,
    summary="Mesures simulées actuelles",
    description=(
        "Génère et retourne des mesures synthétiques fraîches pour l'heure actuelle, "
        "sans les stocker en mémoire permanente. "
        + SYNTHETIC_WARNING
    ),
)
async def get_current(
    request: Request,
    city: Annotated[Optional[str], Query(description="Filtrer par ville")] = None,
    anomaly_mode: Annotated[Optional[bool], Query(description="Activer le mode anomalie")] = None,
):
    """Génère des mesures synthétiques actuelles à la volée."""
    generator: SyntheticWeatherGenerator = request.app.state.generator
    validated_city = _validate_city(city)

    # Déterminer les villes à simuler
    if validated_city:
        if validated_city not in settings.CITIES:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Ville '{validated_city}' non disponible. "
                    f"Villes disponibles : {', '.join(settings.CITIES)}"
                ),
            )
        cities = [validated_city]
    else:
        cities = settings.CITIES

    # Surcharge locale du mode anomalie pour cet appel
    use_anomaly = anomaly_mode if anomaly_mode is not None else generator.anomaly_mode
    original_mode = generator.anomaly_mode
    generator.anomaly_mode = use_anomaly

    try:
        now = datetime.now(timezone.utc)
        measurements = generator.generate_batch(cities=cities, reference_time=now)
    finally:
        # Restaurer le mode original
        generator.anomaly_mode = original_mode

    contains_anomalies = any(m.is_synthetic_anomaly for m in measurements)
    batch = WeatherBatch(
        count=len(measurements),
        measurements=measurements,
        contains_anomalies=contains_anomalies,
    )

    return {
        "warning": SYNTHETIC_WARNING,
        "batch": batch.model_dump(),
    }


@router.get(
    "/history",
    response_model=dict,
    summary="Historique des données synthétiques",
    description=(
        "Retourne l'historique des mesures synthétiques stockées en mémoire "
        "avec filtrage par ville, plage temporelle et mode anomalie. "
        + SYNTHETIC_WARNING
    ),
)
async def get_history(
    request: Request,
    city: Annotated[Optional[str], Query(description="Filtrer par ville")] = None,
    start_time: Annotated[
        Optional[str], Query(description="Borne inférieure ISO 8601 (ex: 2024-01-15T00:00:00Z)")
    ] = None,
    end_time: Annotated[
        Optional[str], Query(description="Borne supérieure ISO 8601")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Nombre max de résultats (1-1000)")] = 100,
    include_anomalies: Annotated[bool, Query(description="Inclure les mesures anomalies")] = True,
):
    """Retourne l'historique filtré des mesures synthétiques."""
    store: WeatherDataStore = request.app.state.store

    # Validation des paramètres
    validated_city = _validate_city(city)
    validated_start = _validate_iso_timestamp(start_time, "start_time")
    validated_end = _validate_iso_timestamp(end_time, "end_time")

    measurements = store.get_history(
        city=validated_city,
        start_time=validated_start,
        end_time=validated_end,
        limit=limit,
        include_anomalies=include_anomalies,
    )

    anomaly_count = sum(1 for m in measurements if m.is_synthetic_anomaly)

    return {
        "warning": SYNTHETIC_WARNING,
        "filters_applied": {
            "city": validated_city,
            "start_time": validated_start,
            "end_time": validated_end,
            "limit": limit,
            "include_anomalies": include_anomalies,
        },
        "total_returned": len(measurements),
        "anomaly_count": anomaly_count,
        "measurements": [m.model_dump() for m in measurements],
    }


@router.get(
    "/generate",
    response_model=dict,
    summary="Générer un nouveau lot de données",
    description=(
        "Génère et stocke un nouveau lot de mesures synthétiques. "
        "Permet de déclencher manuellement une génération. "
        + SYNTHETIC_WARNING
    ),
)
async def generate_data(
    request: Request,
    city: Annotated[Optional[str], Query(description="Générer pour une ville spécifique")] = None,
    force_anomaly: Annotated[bool, Query(description="Forcer l'injection d'anomalies")] = False,
    hours_history: Annotated[
        Optional[int], Query(ge=1, le=168, description="Générer N heures d'historique (1-168)")
    ] = None,
):
    """Génère et stocke un nouveau lot de mesures synthétiques."""
    generator: SyntheticWeatherGenerator = request.app.state.generator
    store: WeatherDataStore = request.app.state.store

    validated_city = _validate_city(city)
    cities = [validated_city] if validated_city else settings.CITIES

    if validated_city and validated_city not in settings.CITIES:
        raise HTTPException(
            status_code=404,
            detail=f"Ville '{validated_city}' non disponible. Villes : {', '.join(settings.CITIES)}",
        )

    # Générer un historique ou une mesure instantanée
    if hours_history:
        measurements = generator.generate_historical_batch(
            hours_back=hours_history, cities=cities
        )
    else:
        now = datetime.now(timezone.utc)
        if force_anomaly:
            # Forcer les anomalies sur toutes les mesures de ce lot
            measurements = []
            for c in cities:
                m = generator.generate_measurement(c, now, force_anomaly=True)
                measurements.append(m)
        else:
            measurements = generator.generate_batch(cities=cities, reference_time=now)

    count = store.add_batch(measurements)
    contains_anomalies = any(m.is_synthetic_anomaly for m in measurements)

    logger.info(
        "Génération manuelle : %d mesures (anomalies=%s, historique=%s)",
        count,
        contains_anomalies,
        hours_history,
    )

    return {
        "warning": SYNTHETIC_WARNING,
        "message": f"{count} mesures synthétiques générées et stockées.",
        "count": count,
        "contains_anomalies": contains_anomalies,
        "anomaly_count": sum(1 for m in measurements if m.is_synthetic_anomaly),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measurements": [m.model_dump() for m in measurements],
    }


@router.get(
    "/export",
    summary="Exporter les données",
    description=(
        "Exporte les données synthétiques en JSON ou CSV. "
        + SYNTHETIC_WARNING
    ),
)
async def export_data(
    request: Request,
    format: Annotated[str, Query(description="Format d'export : 'json' ou 'csv'")] = "json",
    city: Annotated[Optional[str], Query(description="Filtrer par ville")] = None,
    limit: Annotated[int, Query(ge=1, le=10000, description="Nombre max de mesures")] = 1000,
):
    """Exporte les données synthétiques en JSON ou CSV."""
    store: WeatherDataStore = request.app.state.store
    validated_city = _validate_city(city)

    # Valider le format (allow-list)
    if format not in ("json", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Format invalide. Utilisez 'json' ou 'csv'.",
        )

    try:
        if format == "json":
            filepath = store.export_to_json(city=validated_city, limit=limit)
        else:
            filepath = store.export_to_csv(city=validated_city, limit=limit)
    except Exception as exc:
        # Log l'erreur sans exposer les détails internes
        logger.error("Erreur lors de l'export : %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Erreur lors de l'export. Consultez les logs.")

    return {
        "warning": SYNTHETIC_WARNING,
        "message": f"Export {format.upper()} créé avec succès.",
        "filepath": filepath,
        "format": format,
        "city_filter": validated_city,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
