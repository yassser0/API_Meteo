"""
Stockage en mémoire des mesures météorologiques synthétiques.

Ce module gère un store en mémoire (collections Python) pour conserver
les mesures générées. Il fournit également des fonctions d'export CSV/JSON.

AVERTISSEMENT : Toutes les données stockées sont synthétiques.
"""

import csv
import json
import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from app.models import WeatherMeasurement
from app.config import settings

logger = logging.getLogger(__name__)


class WeatherDataStore:
    """
    Stockage en mémoire des mesures météorologiques synthétiques.

    Utilise un deque avec taille maximale par ville pour éviter
    une consommation mémoire excessive.
    """

    def __init__(self, max_records_per_city: int = settings.MAX_RECORDS_IN_MEMORY):
        # dict[city -> deque[WeatherMeasurement]] avec taille bornée
        self._data: dict[str, deque[WeatherMeasurement]] = defaultdict(
            lambda: deque(maxlen=max_records_per_city)
        )
        self.max_records_per_city = max_records_per_city
        logger.info("DataStore initialisé (max %d mesures/ville)", max_records_per_city)

    def add_measurement(self, measurement: WeatherMeasurement) -> None:
        """Ajoute une mesure au store."""
        self._data[measurement.city].append(measurement)
        logger.debug("Mesure ajoutée pour %s", measurement.city)

    def add_batch(self, measurements: list[WeatherMeasurement]) -> int:
        """
        Ajoute un lot de mesures. Retourne le nombre de mesures ajoutées.
        """
        for m in measurements:
            self.add_measurement(m)
        logger.info("%d mesures ajoutées au store", len(measurements))
        return len(measurements)

    def get_latest(self, city: Optional[str] = None) -> list[WeatherMeasurement]:
        """
        Retourne la dernière mesure pour chaque ville.
        Si city est spécifié, retourne uniquement pour cette ville.
        """
        if city is not None:
            city = self._sanitize_city_name(city)
            if city not in self._data or not self._data[city]:
                return []
            return [self._data[city][-1]]

        result = []
        for c, records in self._data.items():
            if records:
                result.append(records[-1])
        return result

    def get_history(
        self,
        city: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        include_anomalies: bool = True,
    ) -> list[WeatherMeasurement]:
        """
        Retourne l'historique filtré des mesures.

        Args:
            city: Filtre par ville (optionnel).
            start_time: ISO 8601 - borne inférieure du timestamp.
            end_time: ISO 8601 - borne supérieure du timestamp.
            limit: Nombre max de résultats (1-1000).
            include_anomalies: Si False, exclut les mesures anomalies.

        Returns:
            Liste de mesures triées du plus récent au plus ancien.
        """
        # Collecter toutes les mesures selon le filtre ville
        if city is not None:
            city = self._sanitize_city_name(city)
            all_records = list(self._data.get(city, []))
        else:
            all_records = []
            for records in self._data.values():
                all_records.extend(records)

        # Filtre anomalies
        if not include_anomalies:
            all_records = [r for r in all_records if not r.is_synthetic_anomaly]

        # Filtre temporel
        if start_time or end_time:
            all_records = self._filter_by_time(all_records, start_time, end_time)

        # Trier du plus récent au plus ancien
        def safe_sort_key(m: WeatherMeasurement):
            if m.timestamp and not m.timestamp.startswith("NOT_A_VALID"):
                try:
                    return m.timestamp
                except Exception:
                    pass
            return m.ingestion_timestamp or ""

        all_records.sort(key=safe_sort_key, reverse=True)

        # Appliquer la limite
        limit = max(1, min(limit, 1000))
        return all_records[:limit]

    def get_total_count(self) -> int:
        """Retourne le nombre total de mesures en mémoire."""
        return sum(len(records) for records in self._data.values())

    def get_cities(self) -> list[str]:
        """Retourne la liste des villes ayant des données."""
        return list(self._data.keys())

    def clear(self) -> None:
        """Vide le store (utile pour les tests)."""
        self._data.clear()
        logger.warning("DataStore vidé.")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_to_json(
        self,
        filepath: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 1000,
    ) -> str:
        """
        Exporte les données en JSON.

        Returns:
            Chemin absolu du fichier exporté.
        """
        measurements = self.get_history(city=city, limit=limit)
        data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "warning": (
                "DONNÉES SYNTHÉTIQUES : Ces données ne représentent PAS "
                "les conditions météorologiques réelles."
            ),
            "count": len(measurements),
            "measurements": [m.model_dump() for m in measurements],
        }

        if filepath is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            city_part = f"_{city}" if city else "_all_cities"
            filepath = os.path.join(
                settings.EXPORT_DIR, f"meteo_synthetic{city_part}_{ts}.json"
            )

        # Sécurité : valider que le chemin reste dans le répertoire d'export
        filepath = self._safe_export_path(filepath)

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("Export JSON : %s (%d mesures)", filepath, len(measurements))
        return os.path.abspath(filepath)

    def export_to_csv(
        self,
        filepath: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 1000,
    ) -> str:
        """
        Exporte les données en CSV.

        Returns:
            Chemin absolu du fichier exporté.
        """
        measurements = self.get_history(city=city, limit=limit)

        if filepath is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            city_part = f"_{city}" if city else "_all_cities"
            filepath = os.path.join(
                settings.EXPORT_DIR, f"meteo_synthetic{city_part}_{ts}.csv"
            )

        # Sécurité : valider que le chemin reste dans le répertoire d'export
        filepath = self._safe_export_path(filepath)

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

        fieldnames = [
            "id",
            "timestamp",
            "city",
            "temperature_celsius",
            "humidity_percent",
            "pressure_hpa",
            "wind_speed_kmh",
            "precipitation_mm",
            "ingestion_timestamp",
            "is_synthetic_anomaly",
            "anomaly_types",
            "data_source",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            # Commentaire en-tête pour avertir que les données sont synthétiques
            f.write("# DONNÉES SYNTHÉTIQUES - Ne représentent PAS les conditions réelles\n")
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in measurements:
                row = m.model_dump()
                row["anomaly_types"] = "|".join(row.get("anomaly_types", []))
                writer.writerow(row)

        logger.info("Export CSV : %s (%d mesures)", filepath, len(measurements))
        return os.path.abspath(filepath)

    # ------------------------------------------------------------------
    # Méthodes privées
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_city_name(city: str) -> str:
        """
        Sanitize le nom de ville pour éviter toute injection.
        N'accepte que les lettres, chiffres, espaces et tirets.
        """
        import re
        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s\-]", "", city).strip()
        if not cleaned:
            raise ValueError(f"Nom de ville invalide : '{city}'")
        return cleaned

    @staticmethod
    def _filter_by_time(
        records: list[WeatherMeasurement],
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> list[WeatherMeasurement]:
        """Filtre les mesures selon une plage temporelle."""
        filtered = []
        for r in records:
            ts_str = r.timestamp or r.ingestion_timestamp
            if not ts_str or ts_str.startswith("NOT_A_VALID"):
                # Inclure les mesures sans timestamp valide
                filtered.append(r)
                continue
            try:
                # Normaliser le timestamp
                ts = ts_str.replace("Z", "+00:00")
                if start_time:
                    start = start_time.replace("Z", "+00:00")
                    if ts < start:
                        continue
                if end_time:
                    end = end_time.replace("Z", "+00:00")
                    if ts > end:
                        continue
                filtered.append(r)
            except Exception:
                # En cas d'erreur de parsing, inclure quand même la mesure
                filtered.append(r)
        return filtered

    @staticmethod
    def _safe_export_path(filepath: str) -> str:
        """
        Sécurité : Vérifie que le chemin d'export reste dans le répertoire
        autorisé pour éviter les attaques par traversée de répertoire.
        """
        import os
        export_dir = os.path.abspath(settings.EXPORT_DIR)
        abs_path = os.path.abspath(filepath)
        # Vérifier que le chemin commence bien par le répertoire d'export
        # (avec séparateur pour éviter les correspondances partielles)
        if not abs_path.startswith(export_dir + os.sep) and abs_path != export_dir:
            logger.warning(
                "Tentative d'écriture hors du répertoire d'export : %s. "
                "Réinitialisation vers le répertoire par défaut.",
                filepath,
            )
            filename = os.path.basename(abs_path)
            return os.path.join(export_dir, filename)
        return abs_path
