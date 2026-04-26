"""
Weekly cron refresh — fetches contracts from the last 8 days, embeds them, and flags them.

Designed to run as a Railway Cron Service.
Usage:
    python -m transparencia.ingest.cron_refresh
"""

import logging
import subprocess
import sys
from datetime import date, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def run(cmd: list[str]) -> None:
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=True)
    log.info("Done: exit_code=%d", result.returncode)


def main() -> None:
    since = (date.today() - timedelta(days=8)).isoformat()
    log.info("=== SECOP II weekly refresh — since=%s ===", since)

    run([sys.executable, "-m", "transparencia.ingest.secop_pipeline", "--since", since])
    run([sys.executable, "-m", "transparencia.ingest.embed_missing"])
    run([sys.executable, "-m", "transparencia.ingest.flag_contracts"])

    log.info("=== Refresh complete ===")


if __name__ == "__main__":
    main()
