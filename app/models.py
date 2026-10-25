"""
Modèles Pydantic pour les données météorologiques synthétiques.

AVERTISSEMENT : Toutes les données météorologiques sont entièrement
synthétiques et ne représentent pas les conditions météorologiques réelles.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class WeatherMeasurement(BaseModel):
    """
    Représente une mesure météorologique synthétique.
    Ces données sont ENTIÈREMENT SYNTHÉTIQUES.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Identifiant unique")
    timestamp: Optional[str] = Field(None, description="Horodatage de la mesure (ISO 8601)")
    city: str = Field(..., description="Nom de la ville simulée")
    temperature_celsius: Optional[float] = Field(None, description="Température en °C (synthétique)")
    humidity_percent: Optional[float] = Field(None, description="Humidité relative en % (synthétique)")
    pressure_hpa: Optional[float] = Field(None, description="Pression atmosphérique en hPa (synthétique)")
    wind_speed_kmh: Optional[float] = Field(None, description="Vitesse du vent en km/h (synthétique)")
    precipitation_mm: Optional[float] = Field(None, description="Précipitations en mm (synthétique)")
    ingestion_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Horodatage d'ingestion UTC",
    )
    is_synthetic_anomaly: bool = Field(False, description="Indique si la mesure contient une anomalie synthétique")
    anomaly_types: list[str] = Field(default_factory=list, description="Types d'anomalies injectées")
    data_source: str = Field(
        default="synthetic_generator_v1",
        description="Source des données : toujours synthétique",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-15T14:30:00Z",
                "city": "Paris",
                "temperature_celsius": 12.5,
                "humidity_percent": 72.3,
                "pressure_hpa": 1013.25,
                "wind_speed_kmh": 18.7,
                "precipitation_mm": 0.0,
                "ingestion_timestamp": "2024-01-15T14:30:01Z",
                "is_synthetic_anomaly": False,
                "anomaly_types": [],
                "data_source": "synthetic_generator_v1",
            }
        }
    }


class WeatherBatch(BaseModel):
    """Lot de mesures météorologiques synthétiques."""

    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    count: int
    measurements: list[WeatherMeasurement]
    contains_anomalies: bool = False
    warning: str = Field(
        default=(
            "DONNÉES SYNTHÉTIQUES : Ces données météorologiques sont "
            "entièrement générées par simulation et ne représentent "
            "pas les conditions météorologiques réelles."
        )
    )


class HistoryQueryParams(BaseModel):
    """Paramètres de filtrage pour l'historique."""

    city: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    include_anomalies: bool = True

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if v < 1:
            return 1
        if v > 1000:
            return 1000
        return v


class APIInfo(BaseModel):
    """Informations générales sur l'API."""

    name: str
    version: str
    description: str
    warning: str = (
        "DONNÉES SYNTHÉTIQUES : Cette API génère uniquement des données "
        "météorologiques simulées. Elles ne représentent PAS les "
        "conditions météorologiques réelles."
    )
    endpoints: dict
    cities: list[str]
    anomaly_mode_active: bool


class HealthStatus(BaseModel):
    """État de santé de l'API."""

    status: str
    timestamp: str
    uptime_seconds: float
    records_in_memory: int
    scheduler_running: bool
    anomaly_mode: bool
    simulation_interval_seconds: int
