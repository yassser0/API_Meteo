# API Météo Synthétique 🌦️

> **⚠️ AVERTISSEMENT IMPORTANT**  
> Toutes les données météorologiques générées par cette API sont **entièrement synthétiques**.  
> Elles sont produites par simulation algorithmique et **ne représentent PAS les conditions météorologiques réelles**.  
> Aucune API météorologique externe, aucun service Open-Meteo et aucune source de données réelle n'est utilisée.

---

## 📋 Description

API REST complète en Python/FastAPI qui génère des données météorologiques **100% synthétiques** pour :
- Tester des pipelines de données (ex. Databricks Free Edition)
- Simuler des ingestions de flux temps-réel
- Tester la robustesse face aux anomalies de données
- Développer et valider des dashboards météo sans dépendance externe

---

## 🏗️ Structure du projet

```
API_Meteo/
├── app/
│   ├── __init__.py          # Package principal
│   ├── main.py              # Application FastAPI (point d'entrée)
│   ├── config.py            # Configuration centralisée (Pydantic Settings)
│   ├── models.py            # Schémas Pydantic des données
│   ├── generator.py         # Générateur de données synthétiques
│   ├── storage.py           # Store en mémoire + export CSV/JSON
│   ├── scheduler.py         # Planificateur asynchrone
│   └── routers/
│       ├── __init__.py
│       └── weather.py       # Endpoints /weather/*
├── tests/
│   ├── __init__.py
│   └── test_api.py          # Suite de tests automatisés
├── exports/                 # Fichiers exportés (CSV/JSON)
├── .env.example             # Modèle de configuration
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 🚀 Démarrage rapide sous Windows

### 1. Prérequis

- Python 3.11 ou supérieur
- Vérifier : `python --version`

### 2. Créer l'environnement virtuel

```powershell
# Depuis le répertoire API_Meteo
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> Si vous obtenez une erreur de politique d'exécution :
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Installer les dépendances

```powershell
pip install -r requirements.txt
```

### 4. (Optionnel) Configurer l'environnement

```powershell
# Copier le fichier exemple
Copy-Item .env.example .env
# Modifier .env selon vos besoins (bloc-notes ou VS Code)
notepad .env
```

### 5. Lancer l'API

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

L'API est maintenant disponible sur **http://127.0.0.1:8000**

---

## 🧪 Lancer les tests

```powershell
# Activer l'environnement virtuel si ce n'est pas déjà fait
.\venv\Scripts\Activate.ps1

# Lancer tous les tests
pytest

# Avec rapport de couverture
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

---

## 📡 Endpoints disponibles

### Informations générales

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Informations sur l'API |
| `/health` | GET | État de santé de l'API |
| `/docs` | GET | Documentation Swagger interactive |
| `/redoc` | GET | Documentation ReDoc |

### Données météo synthétiques

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/weather/latest` | GET | Dernière mesure par ville |
| `/weather/current` | GET | Mesures fraîches simulées |
| `/weather/history` | GET | Historique avec filtrage |
| `/weather/generate` | GET | Générer un nouveau lot |
| `/weather/export` | GET | Exporter en JSON ou CSV |

---

## 🔍 Tester chaque endpoint

### Avec curl (PowerShell)

```powershell
# Informations API
curl http://127.0.0.1:8000/

# État de santé
curl http://127.0.0.1:8000/health

# Dernière mesure (toutes les villes)
curl http://127.0.0.1:8000/weather/latest

# Dernière mesure pour Paris uniquement
curl "http://127.0.0.1:8000/weather/latest?city=Paris"

# Mesures actuelles simulées
curl http://127.0.0.1:8000/weather/current

# Mesures avec mode anomalie activé
curl "http://127.0.0.1:8000/weather/current?anomaly_mode=true"

# Historique (100 dernières mesures)
curl http://127.0.0.1:8000/weather/history

# Historique filtré
curl "http://127.0.0.1:8000/weather/history?city=Lyon&limit=10&include_anomalies=false"

# Historique avec plage temporelle
curl "http://127.0.0.1:8000/weather/history?start_time=2024-01-01T00:00:00Z&end_time=2024-12-31T23:59:59Z"

# Générer un nouveau lot
curl http://127.0.0.1:8000/weather/generate

# Générer avec anomalies forcées
curl "http://127.0.0.1:8000/weather/generate?force_anomaly=true"

# Générer 24h d'historique
curl "http://127.0.0.1:8000/weather/generate?hours_history=24"

# Exporter en JSON
curl "http://127.0.0.1:8000/weather/export?format=json"

# Exporter en CSV
curl "http://127.0.0.1:8000/weather/export?format=csv&city=Paris&limit=500"
```

### Avec la documentation Swagger

Ouvrir http://127.0.0.1:8000/docs dans votre navigateur pour tester chaque endpoint interactivement.

---

## ⚙️ Configuration

| Variable d'environnement | Défaut | Description |
|--------------------------|--------|-------------|
| `API_METEO_HOST` | `127.0.0.1` | Adresse d'écoute |
| `API_METEO_PORT` | `8000` | Port |
| `API_METEO_SIMULATION_INTERVAL_SECONDS` | `10` | Intervalle de génération auto (secondes) |
| `API_METEO_MAX_RECORDS_IN_MEMORY` | `1000` | Max mesures en mémoire par ville |
| `API_METEO_ANOMALY_MODE` | `false` | Activer le mode anomalie |
| `API_METEO_ANOMALY_PROBABILITY` | `0.1` | Probabilité d'anomalie (0.0–1.0) |
| `API_METEO_EXPORT_DIR` | `exports` | Répertoire des exports |
| `API_METEO_LOG_LEVEL` | `INFO` | Niveau de log (DEBUG/INFO/WARNING/ERROR) |

---

## 🦠 Mode anomalie (pour tester Databricks)

Le mode anomalie injecte des données incorrectes identifiables via le champ `is_synthetic_anomaly: true`.

### Activer le mode anomalie

**Option 1 : Variable d'environnement**
```powershell
$env:API_METEO_ANOMALY_MODE = "true"
$env:API_METEO_ANOMALY_PROBABILITY = "0.2"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Option 2 : Forcer sur un seul appel**
```powershell
curl "http://127.0.0.1:8000/weather/generate?force_anomaly=true"
curl "http://127.0.0.1:8000/weather/current?anomaly_mode=true"
```

### Types d'anomalies disponibles

| Type | Description |
|------|-------------|
| `extreme_temperature` | Température hors plage (>60°C ou <-50°C) |
| `humidity_over_100` | Humidité > 100% (physiquement impossible) |
| `missing_temperature` | `temperature_celsius: null` |
| `duplicate_measurement` | ID préfixé `DUPLICATE-` |
| `missing_timestamp` | `timestamp: null` |
| `invalid_timestamp` | Timestamp non parseable |
| `negative_precipitation` | `precipitation_mm < 0` |

### Exemple de mesure anomalie

```json
{
  "id": "DUPLICATE-abc123",
  "timestamp": null,
  "city": "Paris",
  "temperature_celsius": 75.3,
  "humidity_percent": 145.2,
  "pressure_hpa": 1012.5,
  "wind_speed_kmh": 18.7,
  "precipitation_mm": -12.4,
  "is_synthetic_anomaly": true,
  "anomaly_types": ["extreme_temperature", "missing_timestamp"],
  "data_source": "synthetic_generator_v1"
}
```

---

## 📊 Structure d'une mesure normale

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2024-07-15T14:30:00+00:00",
  "city": "Paris",
  "temperature_celsius": 24.7,
  "humidity_percent": 62.3,
  "pressure_hpa": 1013.5,
  "wind_speed_kmh": 15.2,
  "precipitation_mm": 0.0,
  "ingestion_timestamp": "2024-07-15T14:30:01Z",
  "is_synthetic_anomaly": false,
  "anomaly_types": [],
  "data_source": "synthetic_generator_v1"
}
```

---

## 🔗 Ingestion dans Databricks Free Edition

Pour ingérer les données dans Databricks via HTTP :

```python
# Dans un notebook Databricks
import requests
import json

API_BASE = "http://<votre-ip>:8000"  # Remplacer par l'IP de votre machine

# Récupérer les dernières mesures
response = requests.get(f"{API_BASE}/weather/current")
data = response.json()

# Créer un DataFrame Spark
measurements = data["batch"]["measurements"]
df = spark.createDataFrame(measurements)
df.show()

# Ou en streaming : appeler /weather/generate toutes les N secondes
import time
while True:
    r = requests.get(f"{API_BASE}/weather/generate")
    batch = r.json()["measurements"]
    df = spark.createDataFrame(batch)
    df.write.mode("append").saveAsTable("meteo_synthetique")
    time.sleep(10)
```

> **Note** : Pour que Databricks puisse atteindre l'API, l'hôte doit être accessible réseau.
> Modifiez `API_METEO_HOST=0.0.0.0` uniquement dans un environnement réseau sécurisé.

---

## 🏙️ Villes simulées

Paris · Lyon · Marseille · Bordeaux · Toulouse · Lille · Nice · Nantes · Strasbourg · Montpellier

Chaque ville possède un profil climatique fictif (température de base, humidité, pression, vent) avec :
- Variations saisonnières (sinusoïde annuelle)
- Variations diurnes (plus froid à 5h, plus chaud à 14h)
- Bruit gaussien pour le réalisme
- Cohérence entre variables (ex. humidité corrélée à la température)

---

## 🔒 Sécurité

- **En-têtes HTTP** : `X-Content-Type-Options`, `X-Frame-Options`, `CSP`, `Cache-Control`
- **CORS strict** : Origines autorisées configurables (pas de wildcard `*`)
- **Validation des entrées** : Tous les paramètres query sont validés et sanitisés
- **Pas d'injection** : Noms de ville filtrés par regex, timestamps validés ISO 8601
- **Protection traversée de répertoire** : Chemins d'export vérifiés
- **Méthodes HTTP** : Uniquement GET autorisé (API en lecture seule)

---

## 📄 Licence

Projet éducatif - Données 100% synthétiques.
