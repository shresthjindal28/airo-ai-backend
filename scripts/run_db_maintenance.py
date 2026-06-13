#!/usr/bin/env python3
"""Run database lifecycle maintenance: partitions, transcript archival, audio retention."""

from __future__ import annotations

import argparse
import sys

from app.core.database import SessionLocal
from app.core.logging import get_logger, setup_logging
from app.services.audio_retention_worker import AudioRetentionWorker
from app.services.transcript_archive_worker import TranscriptArchiveWorker

setup_logging()
logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="AIRO database lifecycle maintenance")
    parser.add_argument(
        "--task",
        choices=["transcript-archive", "audio-retention", "all"],
        default="all",
    )
    parser.add_argument("--months-ahead", type=int, default=3)
    parser.add_argument("--retention-months", type=int, default=24)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.task in ("transcript-archive", "all"):
            result = TranscriptArchiveWorker().run(db)
            logger.info("Transcript archive result: %s", result)

        if args.task in ("audio-retention", "all"):
            result = AudioRetentionWorker().run(db)
            logger.info("Audio retention result: %s", result)
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
