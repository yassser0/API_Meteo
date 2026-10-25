"""
Configuration de l'API Météo Synthétique.

AVERTISSEMENT : Toutes les données météorologiques générées par cette API
sont entièrement synthétiques et ne représentent pas les conditions
météorologiques réelles.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Paramètres de configuration de l'application."""

    # Informations de l'API
    APP_NAME: str = "API Météo Synthétique"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "API REST générant des données météorologiques synthétiques. "
        "AVERTISSEMENT : Les données sont entièrement synthétiques et "
        "ne représentent PAS les conditions météorologiques réelles."
    )

    # Serveur
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = False

    # Simulation
    # Intervalle en secondes entre chaque génération automatique de données
    SIMULATION_INTERVAL_SECONDS: int = 10
    # Nombre maximum de mesures conservées en mémoire par ville
    MAX_RECORDS_IN_MEMORY: int = 1000
    # Nombre de mesures générées par lot
    BATCH_SIZE: int = 1

    # Villes simulées
    CITIES: List[str] = [
        "Paris",
        "Lyon",
        "Marseille",
        "Bordeaux",
        "Toulouse",
        "Lille",
        "Nice",
        "Nantes",
        "Strasbourg",
        "Montpellier",
    ]

    # Anomalies synthétiques
    # Activer le mode anomalie (False par défaut pour des données cohérentes)
    ANOMALY_MODE: bool = False
    # Probabilité d'injection d'une anomalie par mesure (0.0 à 1.0)
    ANOMALY_PROBABILITY: float = 0.1

    # Export
    EXPORT_DIR: str = "exports"

    # Logs
    LOG_LEVEL: str = "INFO"

    # CORS - origines autorisées (liste restrictive, pas de wildcard *)
    # TODO(security): En production, remplacer par les origines exactes autorisées
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Variables d'environnement préfixées par API_METEO_
        env_prefix = "API_METEO_"


# Instance singleton des paramètres
settings = Settings()
