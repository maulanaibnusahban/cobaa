"""
KRTI UAV System — Logger Utility
==================================
Colored logging dengan format [SERVICE] message.
Setiap service mendapatkan logger sendiri dengan prefix unik.
"""

import logging
import sys
from config.settings import LOG_LEVEL, LOG_TO_FILE, LOG_FILE_PATH


# ── Warna ANSI untuk terminal ──────────────────────────────────────
_COLORS = {
    "DEBUG":    "\033[36m",     # Cyan
    "INFO":     "\033[32m",     # Green
    "WARNING":  "\033[33m",     # Yellow
    "ERROR":    "\033[31m",     # Red
    "CRITICAL": "\033[35m",     # Magenta
    "RESET":    "\033[0m",
}


class _ColorFormatter(logging.Formatter):
    """Formatter yang menambahkan warna ANSI berdasarkan log level."""

    def format(self, record):
        color = _COLORS.get(record.levelname, _COLORS["RESET"])
        reset = _COLORS["RESET"]

        record.levelname = f"{color}{record.levelname:<7}{reset}"
        record.msg = f"{color}{record.msg}{reset}"

        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Membuat logger dengan nama service.

    Args:
        name: Nama service (e.g. "TELEMETRY", "FIRE_DETECT", "GATEWAY")

    Returns:
        logging.Logger yang sudah dikonfigurasi
    """
    logger = logging.getLogger(name)

    # Jangan tambah handler jika sudah ada
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler dengan warna
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    formatter = _ColorFormatter(
        fmt="%(asctime)s [%(name)-14s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S"
    )
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (opsional)
    if LOG_TO_FILE:
        file_handler = logging.FileHandler(LOG_FILE_PATH)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(name)-14s] %(levelname)-7s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation ke root logger
    logger.propagate = False

    return logger
