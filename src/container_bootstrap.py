"""Container startup helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from src.cli import _configure_logging
from src.config import load_settings
from src.config.constants import ARTIFACT_FILENAME_SUFFIX
from src.pull_from_developers_api import download_yamls

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Download runtime artifacts when the configured directory is empty."""
    settings = load_settings()
    log_path = _configure_logging(settings.log_level, settings.log_format, settings.log_dir)
    artifacts_dir = Path(settings.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if any(artifacts_dir.glob(f"*{ARTIFACT_FILENAME_SUFFIX}")):
        LOGGER.info("event=container_bootstrap_skipped reason=artifacts_present log_file=%s", log_path)
        return

    LOGGER.info("event=container_bootstrap_started log_file=%s", log_path)
    summary = download_yamls(settings=settings, refresh=False, force=False)
    LOGGER.info(
        "event=container_bootstrap_completed artifact_mode=%s discovered=%s processed=%s success=%s skipped=%s failed=%s duration_ms=%s",
        summary.artifact_mode,
        summary.discovered,
        summary.processed,
        summary.success,
        summary.skipped,
        summary.failed,
        summary.duration_ms,
    )


if __name__ == "__main__":
    main()
