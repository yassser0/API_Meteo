"""
Planificateur de génération automatique des données météorologiques.

Lance une tâche de fond qui génère de nouvelles mesures synthétiques
à intervalles réguliers configurables.

AVERTISSEMENT : Toutes les données générées sont synthétiques.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.generator import SyntheticWeatherGenerator
from app.storage import WeatherDataStore

logger = logging.getLogger(__name__)


class WeatherScheduler:
    """
    Planificateur asynchrone pour la génération continue de données
    météorologiques synthétiques.
    """

    def __init__(
        self,
        generator: SyntheticWeatherGenerator,
        store: WeatherDataStore,
        interval_seconds: int = settings.SIMULATION_INTERVAL_SECONDS,
    ):
        self.generator = generator
        self.store = store
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        self._generation_count = 0
        self._last_run: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Indique si le planificateur est actif."""
        return self._running and self._task is not None and not self._task.done()

    @property
    def generation_count(self) -> int:
        """Nombre de générations effectuées depuis le démarrage."""
        return self._generation_count

    @property
    def last_run(self) -> datetime | None:
        """Timestamp de la dernière génération."""
        return self._last_run

    async def _run_loop(self) -> None:
        """Boucle principale du planificateur."""
        logger.info(
            "Planificateur démarré (intervalle : %ds, villes : %s)",
            self.interval_seconds,
            settings.CITIES,
        )
        while self._running:
            try:
                await self._generate_and_store()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                # Log l'erreur sans exposer de détails sensibles à l'utilisateur
                logger.error("Erreur lors de la génération automatique : %s", type(exc).__name__)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

        logger.info("Planificateur arrêté.")

    async def _generate_and_store(self) -> None:
        """Génère et stocke un nouveau lot de mesures."""
        now = datetime.now(timezone.utc)
        measurements = self.generator.generate_batch(
            cities=settings.CITIES,
            reference_time=now,
            batch_size=settings.BATCH_SIZE,
        )
        count = self.store.add_batch(measurements)
        self._generation_count += 1
        self._last_run = now
        logger.info(
            "Génération #%d : %d mesures synthétiques ajoutées à %s",
            self._generation_count,
            count,
            now.isoformat(),
        )

    def start(self) -> None:
        """Démarre le planificateur en tâche de fond asyncio."""
        if self.is_running:
            logger.warning("Planificateur déjà en cours d'exécution.")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Planificateur démarré.")

    async def stop(self) -> None:
        """Arrête proprement le planificateur."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Planificateur arrêté proprement.")

    def update_interval(self, new_interval: int) -> None:
        """
        Met à jour l'intervalle de génération.
        Les changements prennent effet au prochain cycle.
        """
        if new_interval < 1:
            raise ValueError("L'intervalle doit être d'au moins 1 seconde.")
        old_interval = self.interval_seconds
        self.interval_seconds = new_interval
        logger.info(
            "Intervalle mis à jour : %ds -> %ds",
            old_interval,
            new_interval,
        )
