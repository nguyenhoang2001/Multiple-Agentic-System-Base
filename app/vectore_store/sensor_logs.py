"""Live sensor logs reader.

Reads sensor log CSV files directly at query time — no embedding is performed.
This corresponds to the "Dynamic — read direct" part of the RAG store in the
IoT smart home architecture.

The CSV files are expected under SENSOR_LOGS_PATH (default: knowledge_base/sensor_logs/).
Expected CSV columns: timestamp, device_id, sensor_type, value, unit, status

Typical usage
-------------
    from app.vectore_store.sensor_logs import read_sensor_logs

    # All recent logs
    logs = read_sensor_logs()

    # Filter by device
    logs = read_sensor_logs(device_id="thermostat_01")

    # Filter by device and sensor type
    logs = read_sensor_logs(device_id="thermostat_01", sensor_type="temperature")
"""

from __future__ import annotations

import csv
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SENSOR_LOGS_PATH: str = os.environ.get("SENSOR_LOGS_PATH", "knowledge_base/sensor_logs")


def read_sensor_logs(
    device_id: Optional[str] = None,
    sensor_type: Optional[str] = None,
    last_n: int = 50,
) -> str:
    """
    Read sensor log CSV files and return a formatted string of recent readings.

    Files are read directly from disk on every call so the data is always fresh.

    Parameters
    ----------
    device_id:
        Filter by device ID (case-insensitive). If None, all devices are included.
    sensor_type:
        Filter by sensor type (e.g. ``'temperature'``, ``'humidity'``, ``'brightness'``).
        If None, all sensor types are included.
    last_n:
        Maximum number of most-recent records to return after filtering.

    Returns
    -------
    str
        Human-readable sensor log entries, most recent first.
        Returns an error string if the logs directory is missing or no rows match.
    """
    if not os.path.isdir(SENSOR_LOGS_PATH):
        return (
            f"Sensor logs directory not found at '{SENSOR_LOGS_PATH}'. "
            "Ensure SENSOR_LOGS_PATH is set correctly."
        )

    all_rows: list[dict] = []
    for filename in sorted(os.listdir(SENSOR_LOGS_PATH)):
        if not filename.endswith(".csv"):
            continue
        filepath = os.path.join(SENSOR_LOGS_PATH, filename)
        try:
            with open(filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (
                        device_id
                        and row.get("device_id", "").lower() != device_id.lower()
                    ):
                        continue
                    if (
                        sensor_type
                        and row.get("sensor_type", "").lower() != sensor_type.lower()
                    ):
                        continue
                    all_rows.append(row)
        except Exception as exc:
            logger.warning("Failed to read sensor log '%s': %s", filepath, exc)

    if not all_rows:
        return "No sensor log entries found matching the query."

    # Return only the most recent `last_n` records (CSV is chronologically ordered)
    recent = all_rows[-last_n:]

    lines = [f"Sensor Logs ({len(recent)} entries, most recent last):"]
    for row in recent:
        ts = row.get("timestamp", "?")
        dev = row.get("device_id", "?")
        stype = row.get("sensor_type", "?")
        val = row.get("value", "?")
        unit = row.get("unit", "")
        status = row.get("status", "?")
        unit_str = f" {unit}" if unit else ""
        lines.append(f"  [{ts}] {dev} / {stype}: {val}{unit_str} (status: {status})")

    return "\n".join(lines)
