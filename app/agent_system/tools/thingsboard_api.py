"""CoreIoT / Thingsboard device-api-controller helpers.

Control flow
------------
  Control (server → device) via Server-Side RPC:
      1. POST /api/auth/login  → JWT token
      2. GET  /api/v1/{token}/attributes?clientKeys=led  → current state
      3. POST /api/plugins/rpc/twoway/{deviceId}
             X-Authorization: Bearer {JWT}
             body: {"method": "setValue", "params": {"led": true}}
         Device responds: {"led": true}

  Read current state:
      GET /api/v1/{token}/attributes?clientKeys=led
      Returns client attributes published by the firmware via sendAttributeData.

Firmware RPC methods (HardwareTest_CoreIoT/src/main.cpp):
  setValue    — params: {"led": <bool>}
  toggleValue — params: {}

Credentials (from .env):
  COREIOT_USERNAME, COREIOT_PASSWORD  — used once per process to get JWT
  COREIOT_API_BASE                    — default https://app.coreiot.io

Device YAML must include device_id (UUID) alongside device_token for RPC.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

COREIOT_API_BASE: str = os.environ.get(
    "COREIOT_API_BASE", "https://app.coreiot.io"
).rstrip("/")
HTTP_TIMEOUT_SECONDS: float = float(os.environ.get("COREIOT_HTTP_TIMEOUT", "10"))
RPC_TIMEOUT_SECONDS: float = float(os.environ.get("COREIOT_RPC_TIMEOUT", "10"))
COREIOT_USERNAME: str = os.environ.get("COREIOT_USERNAME", "")
COREIOT_PASSWORD: str = os.environ.get("COREIOT_PASSWORD", "")


# ---------------------------------------------------------------------------
# JWT cache — login once, reuse until 401. Auto-refresh every 5 minutes.
# ---------------------------------------------------------------------------

import time

_jwt_token: str | None = None
_refresh_token: str | None = None
_jwt_lock = threading.Lock()
_refresh_thread_started = False


def _continuous_refresh() -> None:
    """Daemon thread that refreshes the JWT token every 5 minutes."""
    global _jwt_token, _refresh_token
    while True:
        time.sleep(300)  # 5 minutes
        with _jwt_lock:
            if not _refresh_token:
                continue
            try:
                with httpx.Client() as client:
                    url = f"{COREIOT_API_BASE}/api/auth/token"
                    resp = client.post(
                        url,
                        json={"refreshToken": _refresh_token},
                        timeout=HTTP_TIMEOUT_SECONDS,
                    )
                    if resp.is_success:
                        data = resp.json()
                        _jwt_token = data.get("token", _jwt_token)
                        _refresh_token = data.get("refreshToken", _refresh_token)
                        logger.info("CoreIoT JWT token refreshed successfully.")
                    else:
                        logger.warning(
                            "Failed to refresh JWT token: status=%s body=%s",
                            resp.status_code, resp.text,
                        )
                        _jwt_token = None
                        _refresh_token = None
            except Exception as exc:
                logger.error("Error refreshing JWT token: %s", exc)
                _jwt_token = None
                _refresh_token = None


def _get_jwt(client: httpx.Client) -> str:
    """Login to CoreIoT and return a JWT token. Cached per process."""
    global _jwt_token, _refresh_token, _refresh_thread_started
    with _jwt_lock:
        if _jwt_token:
            return _jwt_token
        if not COREIOT_USERNAME or not COREIOT_PASSWORD:
            raise ValueError(
                "COREIOT_USERNAME and COREIOT_PASSWORD must be set in .env for RPC control."
            )
        url = f"{COREIOT_API_BASE}/api/auth/login"
        resp = client.post(
            url,
            json={"username": COREIOT_USERNAME, "password": COREIOT_PASSWORD},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        if not resp.is_success:
            logger.error(
                "CoreIoT login failed: status=%s body=%s username=%s",
                resp.status_code, resp.text, COREIOT_USERNAME,
            )
        resp.raise_for_status()
        data = resp.json()
        _jwt_token = data["token"]
        _refresh_token = data.get("refreshToken")
        logger.info("CoreIoT JWT obtained for user=%s", COREIOT_USERNAME)

        if not _refresh_thread_started:
            threading.Thread(target=_continuous_refresh, daemon=True).start()
            _refresh_thread_started = True

        return _jwt_token


def _invalidate_jwt() -> None:
    """Clear cached JWT so next call re-authenticates."""
    global _jwt_token, _refresh_token
    with _jwt_lock:
        _jwt_token = None
        _refresh_token = None



# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_keys(shared_attributes: Any) -> list[str]:
    """Extract attribute key names from a flexible input (dict, list, or scalar)."""
    if shared_attributes is None:
        return []
    if isinstance(shared_attributes, dict):
        return [str(k) for k in shared_attributes.keys()]
    if isinstance(shared_attributes, (list, tuple, set)):
        return [str(k) for k in shared_attributes]
    return [str(shared_attributes)]


def _get_client_attributes(
    client: httpx.Client,
    token: str,
    keys: Iterable[str] | None,
) -> dict[str, Any]:
    """GET /api/v1/{token}/attributes?clientKeys=<keys>

    Reads client attributes published by the firmware via sendAttributeData.
    Normalises both flat and nested {"client": {...}} response envelopes.
    """
    url = f"{COREIOT_API_BASE}/api/v1/{token}/attributes"
    params: dict[str, str] = {}
    keys_list = [k for k in (keys or []) if k]
    if keys_list:
        params["clientKeys"] = ",".join(keys_list)

    response = client.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json() if response.content else {}
    if not isinstance(payload, dict):
        return {}
    # Flatten nested {"client": {...}, "shared": {...}} envelope if present.
    if any(k in payload for k in ("client", "shared")):
        flat: dict[str, Any] = {}
        for scope in ("client", "shared"):
            if isinstance(payload.get(scope), dict):
                flat.update(payload[scope])
        return flat
    return payload


def _call_rpc(
    client: httpx.Client,
    jwt: str,
    device_id: str,
    method: str,
    params: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """POST /api/plugins/rpc/twoway/{deviceId} — server-side RPC to device.

    Args:
        jwt:       Bearer token from /api/auth/login
        device_id: Device UUID (not access token)
        method:    RPC method on firmware (e.g. "setValue")
        params:    Passed to device handler e.g. {"led": True}

    Returns:
        (status_code, response_body) — device's response e.g. {"led": True}
    """
    url = f"{COREIOT_API_BASE}/api/plugins/rpc/twoway/{device_id}"
    headers = {"X-Authorization": f"Bearer {jwt}"}
    body = {"method": method, "params": params}
    response = client.post(url, json=body, headers=headers, timeout=RPC_TIMEOUT_SECONDS)
    response.raise_for_status()
    resp_data = response.json() if response.content else {}
    return response.status_code, resp_data if isinstance(resp_data, dict) else {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_shared_attributes(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read current client attributes from CoreIoT for each device.

    Uses GET /api/v1/{token}/attributes?clientKeys=<keys>.
    Firmware publishes state via sendAttributeData (client scope).

    Returns
    -------
    list[dict]::

        {
            "name_device": "Đèn trần",
            "token":       "xdF2nW4aR9SAdqqPiym0",
            "room":        "living_room",
            "shared":      {"led": True},
            "status":      200,
            "error":       None,
        }
    """
    if not devices:
        return []

    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        for device in devices:
            token = device.get("token")
            entry: dict[str, Any] = {
                "name_device": device.get("name_device"),
                "token": token,
                "room": device.get("room"),
                "shared": {},
                "status": None,
                "error": None,
            }
            if not token:
                entry["error"] = "Missing 'token' in device entry."
                results.append(entry)
                continue

            keys = _extract_keys(device.get("shared_attributes"))
            try:
                entry["shared"] = _get_client_attributes(client, token, keys)
                entry["status"] = 200
                logger.debug(
                    "read_shared_attributes OK: %s (%s) keys=%s → %s",
                    device.get("name_device"), token, keys, entry["shared"],
                )
            except httpx.HTTPStatusError as exc:
                entry["status"] = exc.response.status_code
                entry["error"] = f"HTTP {exc.response.status_code}: {exc.response.text}"
                logger.warning(
                    "read_shared_attributes HTTP error: device=%s status=%s body=%s",
                    device.get("name_device"), exc.response.status_code, exc.response.text,
                )
            except httpx.TimeoutException:
                entry["error"] = f"Timeout ({HTTP_TIMEOUT_SECONDS}s)"
                logger.warning(
                    "read_shared_attributes timeout: device=%s token=%s",
                    device.get("name_device"), token,
                )
            except httpx.RequestError as exc:
                entry["error"] = f"Could not reach CoreIoT at {COREIOT_API_BASE}: {exc}"
                logger.warning(
                    "read_shared_attributes network error: device=%s error=%s",
                    device.get("name_device"), exc,
                )
            except Exception as exc:  # noqa: BLE001
                entry["error"] = f"Unexpected error: {exc}"
                logger.exception(
                    "read_shared_attributes unexpected error: device=%s token=%s",
                    device.get("name_device"), token,
                )

            results.append(entry)

    return results


def post_shared_attributes(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Control devices via Server-Side RPC, with a client-attribute diff check.

    Steps per device:
    1. Login to CoreIoT → JWT (cached per process).
    2. GET current client attributes (firmware-published) to diff.
    3. POST /api/plugins/rpc/twoway/{device_id} with setValue if state differs.
    4. Confirm applied state from device RPC response.

    Requires device dict to include ``device_id`` (UUID) alongside ``token``.

    Returns
    -------
    list[dict]::

        {
            "name_device": "Đèn trần",
            "token":       "xdF2nW4aR9SAdqqPiym0",
            "room":        "living_room",
            "before":      {"led": False},
            "after":       {"led": True},
            "posted":      True,
            "status":      200,
            "error":       None,
        }
    """
    if not devices:
        return []

    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        # Get JWT once for this batch
        try:
            jwt = _get_jwt(client)
        except Exception as exc:
            error_msg = f"CoreIoT login failed: {exc}"
            logger.error(error_msg)
            return [
                {
                    "name_device": d.get("name_device"),
                    "token": d.get("token"),
                    "room": d.get("room"),
                    "before": {}, "after": {},
                    "posted": False, "status": None,
                    "error": error_msg,
                }
                for d in devices
            ]

        for device in devices:
            token = device.get("token")
            device_id = device.get("device_id")
            desired: dict[str, Any] = device.get("shared_attributes") or {}
            entry: dict[str, Any] = {
                "name_device": device.get("name_device"),
                "token": token,
                "room": device.get("room"),
                "before": {},
                "after": {},
                "posted": False,
                "status": None,
                "error": None,
            }
            if not token:
                entry["error"] = "Missing 'token' in device entry."
                results.append(entry)
                continue
            if not device_id:
                entry["error"] = "Missing 'device_id' in device entry — required for RPC."
                results.append(entry)
                continue
            if not isinstance(desired, dict) or not desired:
                entry["error"] = "Missing or invalid 'shared_attributes' — nothing to send."
                results.append(entry)
                continue

            try:
                # Step 1 — GET current client attribute state
                current = _get_client_attributes(client, token, list(desired.keys()))
                entry["before"] = current
                logger.debug(
                    "post_shared_attributes GET: device=%s current=%s",
                    device.get("name_device"), current,
                )

                # Step 2 — diff: only RPC for changed attributes
                diff = {k: v for k, v in desired.items() if current.get(k) != v}
                if not diff:
                    entry["after"] = current
                    entry["status"] = 200
                    entry["posted"] = False
                    logger.debug(
                        "post_shared_attributes SKIP (no diff): device=%s desired=%s current=%s",
                        device.get("name_device"), desired, current,
                    )
                    results.append(entry)
                    continue

                # Step 3 — Server-Side RPC setValue
                logger.debug(
                    "post_shared_attributes RPC: device=%s device_id=%s method=setValue params=%s",
                    device.get("name_device"), device_id, diff,
                )
                status_code, rpc_resp = _call_rpc(client, jwt, device_id, "setValue", diff)

                # Step 4 — build after state from RPC response
                applied = {**current, **diff}
                applied.update({k: v for k, v in rpc_resp.items() if k in diff})
                entry["after"] = applied
                entry["status"] = status_code
                entry["posted"] = True
                logger.info(
                    "post_shared_attributes RPC OK: device=%s diff=%s response=%s",
                    device.get("name_device"), diff, rpc_resp,
                )

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    _invalidate_jwt()
                entry["status"] = exc.response.status_code
                entry["error"] = f"HTTP {exc.response.status_code}: {exc.response.text}"
                logger.warning(
                    "post_shared_attributes HTTP error: device=%s status=%s body=%s",
                    device.get("name_device"), exc.response.status_code, exc.response.text,
                )
            except httpx.TimeoutException:
                entry["error"] = f"RPC timeout ({RPC_TIMEOUT_SECONDS}s) — device may be offline."
                logger.warning(
                    "post_shared_attributes RPC timeout: device=%s device_id=%s",
                    device.get("name_device"), device_id,
                )
            except httpx.RequestError as exc:
                entry["error"] = f"Could not reach CoreIoT at {COREIOT_API_BASE}: {exc}"
                logger.warning(
                    "post_shared_attributes network error: device=%s error=%s",
                    device.get("name_device"), exc,
                )
            except Exception as exc:  # noqa: BLE001
                entry["error"] = f"Unexpected error: {exc}"
                logger.exception(
                    "post_shared_attributes unexpected error: device=%s",
                    device.get("name_device"),
                )

            results.append(entry)

    return results


__all__ = [
    "COREIOT_API_BASE",
    "read_shared_attributes",
    "post_shared_attributes",
]
