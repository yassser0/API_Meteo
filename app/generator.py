"""
Générateur de données météorologiques synthétiques.

Ce module génère des données météorologiques 100% synthétiques avec :
- Variations diurnes (jour/nuit)
- Variations saisonnières
- Conditions météo cohérentes entre les variables
- Mode anomalie pour tester la robustesse des pipelines

AVERTISSEMENT : Toutes les données sont entièrement synthétiques et
ne représentent PAS les conditions météorologiques réelles.
"""

import math
import random
import logging
from datetime import datetime, timezone
from typing import Optional

from app.models import WeatherMeasurement
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paramètres climatiques de base par ville (synthétiques)
# Ces valeurs sont fictives et servent uniquement à la simulation
# ---------------------------------------------------------------------------
CITY_CLIMATE_PROFILES: dict[str, dict] = {
    "Paris": {
        "base_temp": 12.0,
        "temp_amplitude": 8.0,
        "base_humidity": 75.0,
        "base_pressure": 1012.0,
        "base_wind": 15.0,
        "precipitation_prob": 0.3,
        "latitude_factor": 0.0,  # référence
    },
    "Lyon": {
        "base_temp": 13.5,
        "temp_amplitude": 9.0,
        "base_humidity": 70.0,
        "base_pressure": 1010.0,
        "base_wind": 12.0,
        "precipitation_prob": 0.25,
        "latitude_factor": -0.5,
    },
    "Marseille": {
        "base_temp": 17.0,
        "temp_amplitude": 7.0,
        "base_humidity": 60.0,
        "base_pressure": 1015.0,
        "base_wind": 22.0,
        "precipitation_prob": 0.15,
        "latitude_factor": -2.0,
    },
    "Bordeaux": {
        "base_temp": 14.5,
        "temp_amplitude": 8.5,
        "base_humidity": 78.0,
        "base_pressure": 1013.0,
        "base_wind": 14.0,
        "precipitation_prob": 0.35,
        "latitude_factor": -0.8,
    },
    "Toulouse": {
        "base_temp": 15.0,
        "temp_amplitude": 9.5,
        "base_humidity": 68.0,
        "base_pressure": 1011.0,
        "base_wind": 16.0,
        "precipitation_prob": 0.25,
        "latitude_factor": -1.0,
    },
    "Lille": {
        "base_temp": 10.0,
        "temp_amplitude": 7.5,
        "base_humidity": 82.0,
        "base_pressure": 1011.0,
        "base_wind": 18.0,
        "precipitation_prob": 0.40,
        "latitude_factor": 1.5,
    },
    "Nice": {
        "base_temp": 18.0,
        "temp_amplitude": 6.5,
        "base_humidity": 58.0,
        "base_pressure": 1016.0,
        "base_wind": 11.0,
        "precipitation_prob": 0.12,
        "latitude_factor": -2.5,
    },
    "Nantes": {
        "base_temp": 13.0,
        "temp_amplitude": 7.0,
        "base_humidity": 80.0,
        "base_pressure": 1012.5,
        "base_wind": 17.0,
        "precipitation_prob": 0.38,
        "latitude_factor": -0.3,
    },
    "Strasbourg": {
        "base_temp": 11.0,
        "temp_amplitude": 10.0,
        "base_humidity": 76.0,
        "base_pressure": 1009.0,
        "base_wind": 10.0,
        "precipitation_prob": 0.32,
        "latitude_factor": 0.8,
    },
    "Montpellier": {
        "base_temp": 16.5,
        "temp_amplitude": 8.0,
        "base_humidity": 62.0,
        "base_pressure": 1014.0,
        "base_wind": 19.0,
        "precipitation_prob": 0.18,
        "latitude_factor": -1.8,
    },
}


def _get_seasonal_offset(month: int) -> float:
    """
    Calcule le décalage saisonnier de température (en °C).
    Variation sinusoïdale sur l'année : max en juillet, min en janvier.
    """
    # Phase : janvier = -pi/2, juillet = pi/2
    angle = (month - 1) / 12.0 * 2 * math.pi - math.pi / 2
    return 10.0 * math.sin(angle)


def _get_diurnal_offset(hour: int) -> float:
    """
    Calcule le décalage diurne de température (en °C).
    Max à 14h, min à 5h du matin.
    """
    angle = (hour - 5) / 24.0 * 2 * math.pi
    return 5.0 * math.sin(angle)


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Borne une valeur entre min et max."""
    return max(min_val, min(max_val, value))


class SyntheticWeatherGenerator:
    """
    Générateur de mesures météorologiques synthétiques.

    AVERTISSEMENT : Les données générées sont ENTIÈREMENT SYNTHÉTIQUES.
    Elles ne représentent PAS les conditions météorologiques réelles.
    """

    def __init__(self, anomaly_mode: bool = False, anomaly_probability: float = 0.1):
        self.anomaly_mode = anomaly_mode
        self.anomaly_probability = anomaly_probability
        logger.info(
            "Générateur synthétique initialisé. anomaly_mode=%s, anomaly_probability=%.2f",
            anomaly_mode,
            anomaly_probability,
        )

    def generate_normal_measurement(
        self,
        city: str,
        reference_time: Optional[datetime] = None,
    ) -> WeatherMeasurement:
        """
        Génère une mesure météo synthétique cohérente pour une ville donnée.

        Les valeurs tiennent compte de :
        - La saison (mois de l'année)
        - L'heure de la journée (jour/nuit)
        - Le profil climatique fictif de la ville
        - Du bruit gaussien pour le réalisme
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        if city not in CITY_CLIMATE_PROFILES:
            # Ville inconnue : profil générique
            profile = CITY_CLIMATE_PROFILES["Paris"]
            logger.warning("Ville inconnue '%s', utilisation du profil Paris.", city)
        else:
            profile = CITY_CLIMATE_PROFILES[city]

        month = reference_time.month
        hour = reference_time.hour

        # --- Température ---
        seasonal = _get_seasonal_offset(month)
        diurnal = _get_diurnal_offset(hour)
        noise = random.gauss(0, 1.5)
        temperature = (
            profile["base_temp"]
            + profile["temp_amplitude"] * (seasonal / 10.0)
            + diurnal
            + profile.get("latitude_factor", 0.0)
            + noise
        )
        temperature = round(_clamp(temperature, -30.0, 50.0), 2)

        # --- Humidité (corrélée négativement à la température) ---
        temp_effect_on_humidity = -(temperature - profile["base_temp"]) * 0.5
        humidity = profile["base_humidity"] + temp_effect_on_humidity + random.gauss(0, 4)
        humidity = round(_clamp(humidity, 10.0, 99.9), 2)

        # --- Pression atmosphérique ---
        pressure = profile["base_pressure"] + random.gauss(0, 3.0)
        pressure = round(_clamp(pressure, 960.0, 1060.0), 2)

        # --- Vent ---
        wind_speed = profile["base_wind"] + random.gauss(0, 5.0)
        wind_speed = round(_clamp(wind_speed, 0.0, 120.0), 2)

        # --- Précipitations ---
        if random.random() < profile["precipitation_prob"]:
            # Pluie : distribution exponentielle (petites pluies fréquentes)
            precipitation = round(random.expovariate(1.5), 2)
            precipitation = _clamp(precipitation, 0.0, 100.0)
        else:
            precipitation = 0.0

        return WeatherMeasurement(
            timestamp=reference_time.isoformat(),
            city=city,
            temperature_celsius=temperature,
            humidity_percent=humidity,
            pressure_hpa=pressure,
            wind_speed_kmh=wind_speed,
            precipitation_mm=precipitation,
            is_synthetic_anomaly=False,
            anomaly_types=[],
        )

    def inject_anomaly(self, measurement: WeatherMeasurement) -> WeatherMeasurement:
        """
        Injecte une anomalie synthétique dans une mesure normale.
        Retourne la mesure modifiée avec le flag is_synthetic_anomaly=True.
        """
        anomaly_types_applied: list[str] = []

        # Sélectionner aléatoirement 1 ou 2 types d'anomalies
        possible_anomalies = [
            "extreme_temperature",
            "humidity_over_100",
            "missing_temperature",
            "duplicate_measurement",
            "missing_timestamp",
            "invalid_timestamp",
            "negative_precipitation",
        ]
        chosen = random.sample(possible_anomalies, k=random.randint(1, 2))

        data = measurement.model_dump()

        for anomaly_type in chosen:
            if anomaly_type == "extreme_temperature":
                # Température extrême (bien au-delà des plages normales)
                # Ne pas appliquer si missing_temperature est aussi sélectionné
                # (missing_temperature prend la priorité)
                if "missing_temperature" not in chosen:
                    data["temperature_celsius"] = random.choice([
                        round(random.uniform(60.0, 90.0), 2),   # Chaleur extrême
                        round(random.uniform(-80.0, -50.0), 2), # Froid extrême
                    ])
                    anomaly_types_applied.append("extreme_temperature")
                else:
                    # Les deux sont choisis : on applique missing_temperature uniquement
                    pass

            elif anomaly_type == "humidity_over_100":
                # Humidité supérieure à 100% (physiquement impossible)
                data["humidity_percent"] = round(random.uniform(101.0, 200.0), 2)
                anomaly_types_applied.append("humidity_over_100")

            elif anomaly_type == "missing_temperature":
                # Température manquante (None)
                data["temperature_celsius"] = None
                anomaly_types_applied.append("missing_temperature")

            elif anomaly_type == "duplicate_measurement":
                # Conserver les mêmes valeurs (la détection de doublons se fait
                # en comparant les IDs identiques dans le pipeline Databricks)
                data["id"] = "DUPLICATE-" + data["id"]
                anomaly_types_applied.append("duplicate_measurement")

            elif anomaly_type == "missing_timestamp":
                # Timestamp manquant
                data["timestamp"] = None
                anomaly_types_applied.append("missing_timestamp")

            elif anomaly_type == "invalid_timestamp":
                # Timestamp invalide (chaîne non parseable)
                data["timestamp"] = "NOT_A_VALID_DATE_" + str(random.randint(1000, 9999))
                anomaly_types_applied.append("invalid_timestamp")

            elif anomaly_type == "negative_precipitation":
                # Précipitations négatives (impossible physiquement)
                data["precipitation_mm"] = round(random.uniform(-50.0, -0.1), 2)
                anomaly_types_applied.append("negative_precipitation")

        data["is_synthetic_anomaly"] = True
        data["anomaly_types"] = anomaly_types_applied
        return WeatherMeasurement(**data)

    def generate_measurement(
        self,
        city: str,
        reference_time: Optional[datetime] = None,
        force_anomaly: bool = False,
    ) -> WeatherMeasurement:
        """
        Génère une mesure, avec éventuelle injection d'anomalie selon la config.
        """
        measurement = self.generate_normal_measurement(city, reference_time)

        if force_anomaly or (
            self.anomaly_mode and random.random() < self.anomaly_probability
        ):
            measurement = self.inject_anomaly(measurement)
            logger.debug(
                "Anomalie injectée pour %s : %s",
                city,
                measurement.anomaly_types,
            )

        return measurement

    def generate_batch(
        self,
        cities: Optional[list[str]] = None,
        reference_time: Optional[datetime] = None,
        batch_size: int = 1,
    ) -> list[WeatherMeasurement]:
        """
        Génère un lot de mesures pour plusieurs villes.

        Args:
            cities: Liste des villes à simuler. Si None, utilise toutes les villes config.
            reference_time: Horodatage de référence. Si None, utilise l'heure actuelle UTC.
            batch_size: Nombre de mesures par ville.

        Returns:
            Liste de WeatherMeasurement synthétiques.
        """
        if cities is None:
            cities = settings.CITIES
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        measurements: list[WeatherMeasurement] = []
        for city in cities:
            for _ in range(batch_size):
                m = self.generate_measurement(city, reference_time)
                measurements.append(m)

        logger.info(
            "Lot généré : %d mesures pour %d villes à %s",
            len(measurements),
            len(cities),
            reference_time.isoformat(),
        )
        return measurements

    def generate_historical_batch(
        self,
        hours_back: int = 24,
        cities: Optional[list[str]] = None,
    ) -> list[WeatherMeasurement]:
        """
        Génère un historique synthétique des dernières N heures.
        Une mesure par heure par ville.
        """
        from datetime import timedelta

        if cities is None:
            cities = settings.CITIES

        now = datetime.now(timezone.utc)
        measurements: list[WeatherMeasurement] = []

        for h in range(hours_back, 0, -1):
            past_time = now - timedelta(hours=h)
            for city in cities:
                m = self.generate_measurement(city, past_time)
                measurements.append(m)

        logger.info(
            "Historique synthétique généré : %d mesures sur %d heures pour %d villes",
            len(measurements),
            hours_back,
            len(cities),
        )
        return measurements
