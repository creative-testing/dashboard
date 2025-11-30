"""
🔒 Gestionnaire de limites globales pour les jobs de refresh

Utilise PostgreSQL comme arbitre entre les containers (CRON + API).
Évite les crashs RAM en limitant le nombre total de workers.

Architecture:
- CRON: max 8 workers (laisse 2 slots pour l'API)
- API: peut utiliser jusqu'à 10 total (2 slots réservés)
- Zombie cleanup: jobs RUNNING > 45min → ERROR
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from ..models.refresh_job import RefreshJob, JobStatus

# Limites globales
# Tous les workers partagent le même pool de 10 slots max
MAX_API_WORKERS = 10      # API a la priorité, user attend devant l'écran
MAX_CRON_WORKERS = 10     # CRON utilise aussi 10 workers (rate monitor protège)
CRON_SKIP_THRESHOLD = 8   # Si >= 8 jobs running, CRON skip ce cycle
MAX_GLOBAL_WORKERS = 10   # Limite absolue système
ZOMBIE_TIMEOUT_MINUTES = 45  # Jobs RUNNING > 45min = morts


def cleanup_zombie_jobs(db: Session) -> int:
    """
    Nettoie les jobs bloqués en RUNNING depuis trop longtemps.

    Évite le blocage permanent si un worker crash sans mettre à jour le status.

    Returns:
        Nombre de jobs nettoyés
    """
    threshold = datetime.now(timezone.utc) - timedelta(minutes=ZOMBIE_TIMEOUT_MINUTES)

    result = db.execute(
        update(RefreshJob)
        .where(
            RefreshJob.status == JobStatus.RUNNING,
            RefreshJob.started_at < threshold
        )
        .values(
            status=JobStatus.ERROR,
            error=f"Timeout après {ZOMBIE_TIMEOUT_MINUTES}min - marqué zombie",
            finished_at=datetime.now(timezone.utc)
        )
    )

    if result.rowcount > 0:
        db.commit()
        print(f"🧟 Nettoyé {result.rowcount} job(s) zombie(s)")

    return result.rowcount


def get_active_job_count(db: Session) -> int:
    """
    Compte le nombre de jobs actifs globalement.

    Inclut QUEUED (en attente) et RUNNING (en cours).
    """
    count = db.execute(
        select(func.count(RefreshJob.id)).where(
            RefreshJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
        )
    ).scalar()

    return count or 0


def get_running_job_count(db: Session) -> int:
    """
    Compte uniquement les jobs en cours d'exécution (RUNNING).

    Plus précis que get_active_job_count pour mesurer la charge réelle.
    """
    count = db.execute(
        select(func.count(RefreshJob.id)).where(
            RefreshJob.status == JobStatus.RUNNING
        )
    ).scalar()

    return count or 0


def can_cron_proceed(db: Session) -> tuple[bool, int, str]:
    """
    Vérifie si le CRON peut lancer des jobs.

    Le CRON a une priorité BASSE. Si le système est déjà occupé
    (API en train de faire un BASELINE pour un nouvel user),
    le CRON skip ce cycle et réessaie dans 2h. Pas grave.

    Returns:
        (can_proceed, available_slots, message)
    """
    # D'abord, nettoyer les zombies
    cleanup_zombie_jobs(db)

    # Compter les jobs actifs
    running = get_running_job_count(db)

    # Si système déjà bien occupé → CRON skip (priorité à l'API)
    if running >= CRON_SKIP_THRESHOLD:
        return (False, 0, f"⏭️ Système occupé ({running} jobs), CRON skip ce cycle (priorité API)")

    available = min(MAX_CRON_WORKERS, MAX_GLOBAL_WORKERS - running)
    return (True, available, f"✅ {running} jobs en cours, {available} slots disponibles pour CRON")


def can_api_proceed(db: Session) -> tuple[bool, int, str]:
    """
    Vérifie si l'API peut lancer des jobs.

    L'API a la PRIORITÉ HAUTE (nouvel utilisateur qui attend).
    Elle peut utiliser jusqu'à MAX_API_WORKERS (10) slots.

    Returns:
        (can_proceed, available_slots, message)
    """
    # D'abord, nettoyer les zombies
    cleanup_zombie_jobs(db)

    # Compter les jobs actifs
    running = get_running_job_count(db)

    if running >= MAX_API_WORKERS:
        return (False, 0, f"Système très occupé ({running} jobs), réessayez dans quelques minutes")

    available = MAX_API_WORKERS - running
    return (True, available, f"{available} slots disponibles")
