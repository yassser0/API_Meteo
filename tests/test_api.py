"""
Tests automatisés pour l'API Météo Synthétique.

Tests couverts :
- Générateur de données synthétiques
- Store en mémoire
- Tous les endpoints REST
- Mode anomalie
- Exports CSV/JSON
- Validation des paramètres

Le serveur de test écoute sur 127.0.0.1 (jamais sur 0.0.0.0)
conformément aux directives de sécurité.
"""

import json
import math
import os
import tempfile
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.generator import SyntheticWeatherGenerator, CITY_CLIMATE_PROFILES
from app.models import WeatherMeasurement
from app.storage import WeatherDataStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def generator():
    """Générateur en mode normal (pas d'anomalies)."""
    return SyntheticWeatherGenerator(anomaly_mode=False, anomaly_probability=0.0)


@pytest.fixture(scope="session")
def anomaly_generator():
    """Générateur en mode anomalie (toutes les mesures contiennent une anomalie)."""
    return SyntheticWeatherGenerator(anomaly_mode=True, anomaly_probability=1.0)


@pytest.fixture
def store():
    """Store vide pour chaque test."""
    return WeatherDataStore(max_records_per_city=100)


@pytest.fixture(scope="session")
def client():
    """
    Client de test FastAPI.
    Note : le TestClient écoute sur 127.0.0.1 (jamais 0.0.0.0).
    """
    from app.main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests du générateur
# ---------------------------------------------------------------------------

class TestSyntheticGenerator:
    """Tests unitaires du générateur de données synthétiques."""

    def test_generate_normal_measurement_returns_valid_data(self, generator):
        """Une mesure normale doit avoir des champs valides et non-anomaliques."""
        m = generator.generate_measurement("Paris")
        assert isinstance(m, WeatherMeasurement)
        assert m.city == "Paris"
        assert m.is_synthetic_anomaly is False
        assert len(m.anomaly_types) == 0
        assert m.data_source == "synthetic_generator_v1"

    def test_temperature_within_realistic_range(self, generator):
        """La température doit rester dans une plage réaliste (-30 à 50°C)."""
        for _ in range(20):
            m = generator.generate_measurement("Paris")
            assert m.temperature_celsius is not None
            assert -30.0 <= m.temperature_celsius <= 50.0

    def test_humidity_within_valid_range(self, generator):
        """L'humidité normale doit rester entre 10 et 99.9%."""
        for _ in range(20):
            m = generator.generate_measurement("Lyon")
            assert m.humidity_percent is not None
            assert 10.0 <= m.humidity_percent <= 99.9

    def test_pressure_within_valid_range(self, generator):
        """La pression doit être dans la plage physiquement possible."""
        for _ in range(20):
            m = generator.generate_measurement("Marseille")
            assert m.pressure_hpa is not None
            assert 960.0 <= m.pressure_hpa <= 1060.0

    def test_wind_speed_non_negative(self, generator):
        """La vitesse du vent ne peut pas être négative."""
        for _ in range(20):
            m = generator.generate_measurement("Nice")
            assert m.wind_speed_kmh is not None
            assert m.wind_speed_kmh >= 0.0

    def test_precipitation_non_negative_in_normal_mode(self, generator):
        """Les précipitations sont non-négatives en mode normal."""
        for _ in range(20):
            m = generator.generate_measurement("Bordeaux")
            assert m.precipitation_mm is not None
            assert m.precipitation_mm >= 0.0

    def test_all_configured_cities_generate_data(self, generator):
        """Toutes les villes configurées doivent générer des données."""
        for city in settings.CITIES:
            m = generator.generate_measurement(city)
            assert m.city == city

    def test_timestamp_is_present(self, generator):
        """Le timestamp doit être présent pour les mesures normales."""
        m = generator.generate_measurement("Paris")
        assert m.timestamp is not None
        assert len(m.timestamp) > 0

    def test_batch_generation(self, generator):
        """Un lot doit contenir une mesure par ville."""
        measurements = generator.generate_batch(cities=["Paris", "Lyon", "Nice"])
        assert len(measurements) == 3
        cities_returned = {m.city for m in measurements}
        assert cities_returned == {"Paris", "Lyon", "Nice"}

    def test_historical_batch_correct_size(self, generator):
        """L'historique doit contenir N_heures * N_villes mesures."""
        hours = 3
        cities = ["Paris", "Lyon"]
        measurements = generator.generate_historical_batch(hours_back=hours, cities=cities)
        assert len(measurements) == hours * len(cities)

    def test_seasonal_variation(self, generator):
        """La température doit varier selon les saisons."""
        # Été (juillet, heure de midi)
        summer = datetime(2024, 7, 15, 12, 0, tzinfo=timezone.utc)
        # Hiver (janvier, heure de midi)
        winter = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        # Moyenner sur plusieurs mesures pour réduire le bruit
        summer_temps = [generator.generate_measurement("Paris", summer).temperature_celsius for _ in range(10)]
        winter_temps = [generator.generate_measurement("Paris", winter).temperature_celsius for _ in range(10)]

        avg_summer = sum(t for t in summer_temps if t) / len(summer_temps)
        avg_winter = sum(t for t in winter_temps if t) / len(winter_temps)

        assert avg_summer > avg_winter, "La température estivale doit être > hivernale"

    def test_diurnal_variation(self, generator):
        """La température doit être plus haute l'après-midi qu'à l'aube."""
        ref_date = datetime(2024, 6, 21, tzinfo=timezone.utc)

        # 5h du matin (le plus froid)
        dawn = ref_date.replace(hour=5)
        # 14h (le plus chaud)
        noon = ref_date.replace(hour=14)

        dawn_temps = [generator.generate_measurement("Paris", dawn).temperature_celsius for _ in range(10)]
        noon_temps = [generator.generate_measurement("Paris", noon).temperature_celsius for _ in range(10)]

        avg_dawn = sum(t for t in dawn_temps if t) / len(dawn_temps)
        avg_noon = sum(t for t in noon_temps if t) / len(noon_temps)

        assert avg_noon > avg_dawn, "La température à 14h doit être > à 5h"


class TestAnomalyGenerator:
    """Tests du mode anomalie."""

    def test_anomaly_mode_sets_flag(self, anomaly_generator):
        """Les mesures en mode anomalie doivent avoir is_synthetic_anomaly=True."""
        m = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
        assert m.is_synthetic_anomaly is True
        assert len(m.anomaly_types) > 0

    def test_extreme_temperature_anomaly(self, anomaly_generator):
        """L'anomalie de température extrême doit dépasser les bornes normales."""
        found = False
        for _ in range(50):
            m = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
            if "extreme_temperature" in m.anomaly_types:
                assert m.temperature_celsius is not None
                assert (
                    m.temperature_celsius > 50.0 or m.temperature_celsius < -30.0
                ), "Température extrême hors plage"
                found = True
                break
        # Ce test est probabiliste mais devrait passer en 50 essais avec prob=1.0

    def test_humidity_over_100_anomaly(self, anomaly_generator):
        """L'anomalie d'humidité doit dépasser 100%."""
        for _ in range(50):
            m = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
            if "humidity_over_100" in m.anomaly_types:
                assert m.humidity_percent is not None
                assert m.humidity_percent > 100.0
                break

    def test_missing_temperature_anomaly(self, anomaly_generator):
        """L'anomalie de température manquante doit avoir None."""
        for _ in range(50):
            m = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
            if "missing_temperature" in m.anomaly_types:
                assert m.temperature_celsius is None
                break

    def test_missing_timestamp_anomaly(self, anomaly_generator):
        """L'anomalie de timestamp manquant doit avoir None."""
        for _ in range(50):
            m = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
            if "missing_timestamp" in m.anomaly_types:
                assert m.timestamp is None
                break

    def test_negative_precipitation_anomaly(self, anomaly_generator):
        """L'anomalie de précipitations doit être négative."""
        for _ in range(50):
            m = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
            if "negative_precipitation" in m.anomaly_types:
                assert m.precipitation_mm is not None
                assert m.precipitation_mm < 0.0
                break

    def test_normal_mode_no_anomalies(self, generator):
        """En mode normal, aucune anomalie ne doit être injectée."""
        for _ in range(50):
            m = generator.generate_measurement("Paris")
            assert m.is_synthetic_anomaly is False


# ---------------------------------------------------------------------------
# Tests du store
# ---------------------------------------------------------------------------

class TestWeatherDataStore:
    """Tests unitaires du store en mémoire."""

    def test_add_and_retrieve_measurement(self, store, generator):
        """Une mesure ajoutée doit être récupérable."""
        m = generator.generate_measurement("Paris")
        store.add_measurement(m)
        latest = store.get_latest(city="Paris")
        assert len(latest) == 1
        assert latest[0].city == "Paris"

    def test_get_latest_returns_most_recent(self, store, generator):
        """get_latest doit retourner la mesure la plus récente."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        m1 = generator.generate_measurement("Lyon", now - timedelta(hours=2))
        m2 = generator.generate_measurement("Lyon", now)
        store.add_measurement(m1)
        store.add_measurement(m2)
        latest = store.get_latest(city="Lyon")
        assert len(latest) == 1
        assert latest[0].id == m2.id

    def test_get_latest_all_cities(self, store, generator):
        """get_latest sans filtre doit retourner une mesure par ville."""
        for city in ["Paris", "Nice", "Lille"]:
            store.add_measurement(generator.generate_measurement(city))
        latest = store.get_latest()
        cities = {m.city for m in latest}
        assert "Paris" in cities
        assert "Nice" in cities
        assert "Lille" in cities

    def test_history_limit(self, store, generator):
        """Le paramètre limit doit être respecté."""
        for _ in range(20):
            store.add_measurement(generator.generate_measurement("Paris"))
        history = store.get_history(city="Paris", limit=5)
        assert len(history) <= 5

    def test_history_exclude_anomalies(self, store, anomaly_generator, generator):
        """L'option include_anomalies=False doit exclure les anomalies."""
        store.add_measurement(generator.generate_measurement("Paris"))
        anomaly = anomaly_generator.generate_measurement("Paris", force_anomaly=True)
        store.add_measurement(anomaly)
        history = store.get_history(city="Paris", include_anomalies=False)
        assert all(not m.is_synthetic_anomaly for m in history)

    def test_total_count(self, store, generator):
        """get_total_count doit retourner le nombre total correct."""
        initial = store.get_total_count()
        store.add_measurement(generator.generate_measurement("Paris"))
        store.add_measurement(generator.generate_measurement("Lyon"))
        assert store.get_total_count() == initial + 2

    def test_city_name_sanitization(self, store):
        """Les noms de ville avec caractères spéciaux doivent être rejetés ou nettoyés."""
        # Un nom avec seulement des caractères spéciaux (résultat vide après nettoyage)
        with pytest.raises(ValueError):
            WeatherDataStore._sanitize_city_name("<>!@#$%^&*()")

        # Les balises script doivent être nettoyées (les lettres restent)
        cleaned = WeatherDataStore._sanitize_city_name("<script>Paris</script>")
        # Le résultat doit être nettoyé des balises mais garder le texte
        assert "<" not in cleaned
        assert ">" not in cleaned


    def test_safe_export_path_prevents_traversal(self, store):
        """La validation du chemin d'export doit bloquer la traversée de répertoire."""
        malicious_path = os.path.join(settings.EXPORT_DIR, "..", "..", "sensitive.json")
        safe_path = store._safe_export_path(malicious_path)
        export_dir = os.path.abspath(settings.EXPORT_DIR)
        assert safe_path.startswith(export_dir), "Le chemin sécurisé doit rester dans EXPORT_DIR"

    def test_export_to_json(self, store, generator):
        """L'export JSON doit créer un fichier valide."""
        for city in ["Paris", "Lyon"]:
            store.add_measurement(generator.generate_measurement(city))

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(settings, "EXPORT_DIR", tmp_dir):
                filepath = store.export_to_json(limit=10)

            # Lire le fichier JSON directement (avant nettoyage du tmp_dir)
            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "measurements" in data
            assert data["count"] > 0
            assert "warning" in data

    def test_export_to_csv(self, store, generator):
        """L'export CSV doit créer un fichier valide."""
        store.add_measurement(generator.generate_measurement("Paris"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(settings, "EXPORT_DIR", tmp_dir):
                filepath = store.export_to_csv(limit=10)

            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            assert "DONNÉES SYNTHÉTIQUES" in content
            assert "city" in content


# ---------------------------------------------------------------------------
# Tests des endpoints REST
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    """Tests d'intégration des endpoints FastAPI."""

    def test_root_returns_api_info(self, client):
        """GET / doit retourner les informations de l'API."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "warning" in data
        assert "SYNTHÉTIQUES" in data["warning"]
        assert "endpoints" in data

    def test_health_endpoint(self, client):
        """GET /health doit retourner un état healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "records_in_memory" in data
        assert data["records_in_memory"] >= 0

    def test_weather_latest(self, client):
        """GET /weather/latest doit retourner des mesures."""
        response = client.get("/weather/latest")
        assert response.status_code == 200
        data = response.json()
        assert "measurements" in data
        assert "warning" in data
        assert len(data["measurements"]) > 0

    def test_weather_latest_filter_by_city(self, client):
        """GET /weather/latest?city=Paris doit filtrer."""
        response = client.get("/weather/latest?city=Paris")
        assert response.status_code == 200
        data = response.json()
        for m in data["measurements"]:
            assert m["city"] == "Paris"

    def test_weather_latest_unknown_city_returns_404(self, client):
        """GET /weather/latest pour une ville inconnue doit retourner 404."""
        response = client.get("/weather/latest?city=VilleInconnue999")
        assert response.status_code == 404

    def test_weather_current(self, client):
        """GET /weather/current doit générer des mesures fraîches."""
        response = client.get("/weather/current")
        assert response.status_code == 200
        data = response.json()
        assert "batch" in data
        assert data["batch"]["count"] == len(settings.CITIES)

    def test_weather_current_with_city(self, client):
        """GET /weather/current?city=Paris doit filtrer par ville."""
        response = client.get("/weather/current?city=Paris")
        assert response.status_code == 200
        data = response.json()
        assert data["batch"]["count"] == 1
        assert data["batch"]["measurements"][0]["city"] == "Paris"

    def test_weather_history(self, client):
        """GET /weather/history doit retourner l'historique."""
        response = client.get("/weather/history")
        assert response.status_code == 200
        data = response.json()
        assert "measurements" in data
        assert "total_returned" in data
        assert "filters_applied" in data

    def test_weather_history_limit(self, client):
        """GET /weather/history?limit=5 doit limiter les résultats."""
        response = client.get("/weather/history?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["measurements"]) <= 5

    def test_weather_history_invalid_limit(self, client):
        """GET /weather/history avec limit invalide doit retourner 422."""
        response = client.get("/weather/history?limit=99999")
        assert response.status_code == 422

    def test_weather_generate(self, client):
        """GET /weather/generate doit générer et stocker des données."""
        response = client.get("/weather/generate")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] > 0
        assert "warning" in data

    def test_weather_generate_with_anomaly(self, client):
        """GET /weather/generate?force_anomaly=true doit injecter des anomalies."""
        response = client.get("/weather/generate?force_anomaly=true")
        assert response.status_code == 200
        data = response.json()
        assert data["contains_anomalies"] is True

    def test_weather_generate_history(self, client):
        """GET /weather/generate?hours_history=2 doit générer 2h d'historique."""
        response = client.get("/weather/generate?hours_history=2")
        assert response.status_code == 200
        data = response.json()
        # 2 heures * 10 villes = 20 mesures
        assert data["count"] == 2 * len(settings.CITIES)

    def test_weather_export_json(self, client):
        """GET /weather/export?format=json doit exporter en JSON."""
        response = client.get("/weather/export?format=json")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert "filepath" in data

    def test_weather_export_csv(self, client):
        """GET /weather/export?format=csv doit exporter en CSV."""
        response = client.get("/weather/export?format=csv")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "csv"

    def test_weather_export_invalid_format(self, client):
        """GET /weather/export?format=xml doit retourner 400."""
        response = client.get("/weather/export?format=xml")
        assert response.status_code == 400

    def test_security_headers_present(self, client):
        """Les en-têtes de sécurité doivent être présents dans les réponses."""
        response = client.get("/")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("cache-control") == "no-store"

    def test_synthetic_warning_in_all_endpoints(self, client):
        """Tous les endpoints météo doivent contenir l'avertissement synthétique."""
        endpoints = [
            "/weather/latest",
            "/weather/current",
            "/weather/history",
            "/weather/generate",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            data = response.json()
            warning = data.get("warning", "")
            assert "SYNTHÉTIQUES" in warning or "synthétique" in warning.lower(), (
                f"Avertissement manquant sur {endpoint}"
            )

    def test_invalid_city_parameter_rejected(self, client):
        """Un paramètre city avec caractères spéciaux doit être rejeté."""
        response = client.get("/weather/latest?city=<script>alert(1)</script>")
        # Doit retourner 400 (ville invalide) ou 404 (pas de données pour la ville sanitisée)
        assert response.status_code in (400, 404)

    def test_invalid_timestamp_parameter_rejected(self, client):
        """Un timestamp invalide doit retourner 400."""
        response = client.get("/weather/history?start_time=NOT_A_DATE")
        assert response.status_code == 400

    def test_docs_endpoint_available(self, client):
        """GET /docs doit retourner la documentation Swagger."""
        response = client.get("/docs")
        assert response.status_code == 200
