from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .interpretation import evaluate_observations
from .models import AppSettings, DailyObservation, FluidObservation, parse_hhmm_time, parse_iso_date
from .storage import LocalStore
from .taxonomy import (
    BleedingLevel,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    TemperatureDisturbance,
    TemperatureUnit,
)

WEB_ASSET_DIRECTORY = Path(__file__).with_name("web_assets")
MAX_REQUEST_BYTES = 64 * 1024


class DesktopWebServer(ThreadingHTTPServer):
    store: LocalStore


def create_desktop_server(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> DesktopWebServer:
    store = LocalStore(db_path)
    store.initialize()
    server = DesktopWebServer((host, port), DesktopWebHandler)
    server.store = store
    return server


def serve_desktop_app(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    server = create_desktop_server(db_path, host=host, port=port)
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    print(f"SymptoThermal desktop app running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.35, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class DesktopWebHandler(BaseHTTPRequestHandler):
    server: DesktopWebServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json({"status": "ok"})
            return
        if path == "/api/bootstrap":
            self._send_json(_bootstrap_payload(self.server.store))
            return
        self._serve_asset(path)

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
        if self.headers.get("X-Symptothermal-Client") != "desktop-web":
            self._send_error_json(HTTPStatus.FORBIDDEN, "Desktop client header is required.")
            return

        path = urlparse(self.path).path
        try:
            payload = self._read_json_body()
            if path == "/api/settings":
                settings = AppSettings.from_dict(payload)
                self.server.store.save_settings(settings)
                self._send_json(_bootstrap_payload(self.server.store))
                return
            if path.startswith("/api/observations/"):
                observation_date = unquote(path.removeprefix("/api/observations/"))
                observation = _observation_from_web_payload(observation_date, payload)
                settings = self.server.store.load_settings()
                self.server.store.upsert_observation(observation, settings.temperature_unit)
                self._send_json(_bootstrap_payload(self.server.store))
                return
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def log_message(self, format: str, *args: object) -> None:
        print(f"desktop-web: {format % args}")

    def _read_json_body(self) -> dict[str, Any]:
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json.")
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("Request body size is invalid.")
        payload = json.loads(self.rfile.read(content_length))
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object.")
        return payload

    def _serve_asset(self, request_path: str) -> None:
        relative_path = "index.html" if request_path in {"", "/"} else unquote(request_path.lstrip("/"))
        asset_root = WEB_ASSET_DIRECTORY.resolve()
        candidate = (asset_root / relative_path).resolve()
        if not candidate.is_relative_to(asset_root) or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        media_type, _ = mimetypes.guess_type(candidate.name)
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(content)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
            "form-action 'self'",
        )


def _bootstrap_payload(store: LocalStore) -> dict[str, Any]:
    settings = store.load_settings()
    observations = store.list_observations()
    report = evaluate_observations(observations, settings)
    today = date.today()
    today_observation = next(
        (item for item in observations if item.observation_date == today),
        DailyObservation(observation_date=today),
    )
    preview_observations = [item for item in observations if item.observation_date != today]
    preview_observations.append(today_observation)
    preview_report = evaluate_observations(preview_observations, settings)
    today_interpretation: dict[str, Any] | None = None
    for cycle in preview_report.cycles:
        for day_interpretation in cycle.days:
            if day_interpretation.observation_date == today:
                today_interpretation = day_interpretation.as_dict()
                break
        if today_interpretation:
            break

    return {
        "today": today.isoformat(),
        "settings": settings.as_dict(),
        "today_observation": _observation_to_web_payload(today_observation, settings),
        "today_interpretation": today_interpretation,
        "observations": [_observation_to_web_payload(item, settings) for item in observations],
        "report": report.as_dict(),
    }


def _observation_to_web_payload(
    observation: DailyObservation,
    settings: AppSettings,
) -> dict[str, Any]:
    return {
        "date": observation.observation_date.isoformat(),
        "waking_temperature": observation.waking_temperature,
        "temperature_unit": (observation.temperature_unit or settings.temperature_unit).value,
        "temperature_time": (
            observation.temperature_time.strftime("%H:%M")
            if observation.temperature_time
            else settings.default_wake_time
        ),
        "temperature_disturbances": [item.value for item in observation.temperature_disturbances],
        "mucus_sign": _web_mucus_sign(observation.fluid),
        "bleeding": observation.bleeding.value,
        "notes": observation.notes,
    }


def _observation_from_web_payload(
    observation_date: str,
    payload: dict[str, Any],
) -> DailyObservation:
    parsed_date = parse_iso_date(observation_date)
    raw_temperature = payload.get("waking_temperature")
    temperature = None if raw_temperature in {None, ""} else float(raw_temperature)
    unit = TemperatureUnit(payload.get("temperature_unit", TemperatureUnit.CELSIUS.value))
    temperature_time_value = payload.get("temperature_time")
    temperature_time = (
        parse_hhmm_time(temperature_time_value)
        if temperature is not None and temperature_time_value
        else None
    )
    disturbances = [
        TemperatureDisturbance(item)
        for item in payload.get("temperature_disturbances", [])
    ]
    mucus_sign = str(payload.get("mucus_sign", "not_checked"))
    return DailyObservation(
        observation_date=parsed_date,
        waking_temperature=temperature,
        temperature_unit=unit if temperature is not None else None,
        temperature_time=temperature_time,
        temperature_disturbed=bool(disturbances),
        temperature_disturbances=disturbances,
        fluid=_fluid_from_web_sign(mucus_sign),
        bleeding=BleedingLevel(payload.get("bleeding", BleedingLevel.NONE.value)),
        notes=str(payload.get("notes", "")),
    )


def _web_mucus_sign(fluid: FluidObservation | None) -> str:
    if fluid is None:
        return "not_checked"
    return {
        FluidSensation.DRY: "dry",
        FluidSensation.STICKY: "sticky",
        FluidSensation.CREAMY: "creamy",
        FluidSensation.WATERY: "wet",
        FluidSensation.SLIPPERY: "slippery",
    }[fluid.sensation]


def _fluid_from_web_sign(sign: str) -> FluidObservation | None:
    if sign == "not_checked":
        return None
    values = {
        "dry": (FluidSensation.DRY, FluidQuantity.NONE, MucusColor.NONE, MucusTexture.NONE, None),
        "sticky": (FluidSensation.STICKY, FluidQuantity.LOW, MucusColor.CLOUDY, MucusTexture.STICKY, 1),
        "creamy": (FluidSensation.CREAMY, FluidQuantity.MEDIUM, MucusColor.WHITE, MucusTexture.CREAMY, 2),
        "wet": (FluidSensation.WATERY, FluidQuantity.HIGH, MucusColor.CLEAR, MucusTexture.NONE, 4),
        "slippery": (FluidSensation.SLIPPERY, FluidQuantity.HIGH, MucusColor.CLEAR, MucusTexture.STRETCHY, 5),
    }
    try:
        sensation, quantity, color, texture, amount = values[sign]
    except KeyError as exc:
        raise ValueError(f"Unknown mucus sign: {sign}") from exc
    return FluidObservation(
        sensation=sensation,
        quantity=quantity,
        color=color,
        texture=texture,
        amount=amount,
        peak_quality=False,
    )
