import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from symptothermal_nfp.storage import LocalStore
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    FluidSensation,
    TemperatureDisturbance,
    TemperatureUnit,
    TrackingGoal,
)
from symptothermal_nfp.web import create_desktop_server


@pytest.fixture
def desktop_server(tmp_path):
    db_path = tmp_path / "desktop.db"
    server = create_desktop_server(db_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}", LocalStore(db_path)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_desktop_root_serves_computer_first_app(desktop_server) -> None:
    base_url, _ = desktop_server

    with urlopen(f"{base_url}/", timeout=2) as response:
        content = response.read().decode("utf-8")

    assert response.status == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Stored on this computer" in content
    assert "Daily observations" in content
    assert "Cycle history" in content


def test_bootstrap_includes_today_preview_and_plain_language_feedback(desktop_server) -> None:
    base_url, _ = desktop_server

    payload = _get_json(f"{base_url}/api/bootstrap")

    assert payload["settings"]["setup_complete"] is False
    assert payload["today_observation"]["mucus_sign"] == "not_checked"
    assert payload["today_interpretation"]["feedback"]["headline"] == "Not enough information"
    assert payload["report"]["rule_pack_version"] == "stm-v1"


def test_settings_and_observation_round_trip_through_desktop_api(desktop_server) -> None:
    base_url, store = desktop_server
    bootstrap = _get_json(f"{base_url}/api/bootstrap")
    settings = {
        **bootstrap["settings"],
        "temperature_unit": "fahrenheit",
        "tracking_goal": "avoid_pregnancy",
        "default_wake_time": "06:10",
        "setup_complete": True,
    }

    updated = _put_json(f"{base_url}/api/settings", settings)
    today = updated["today"]
    observation = {
        "waking_temperature": 97.62,
        "temperature_unit": "fahrenheit",
        "temperature_time": "06:12",
        "temperature_disturbances": ["poor_sleep"],
        "mucus_sign": "wet",
        "bleeding": "medium",
        "notes": "Desktop entry",
    }
    result = _put_json(f"{base_url}/api/observations/{today}", observation)

    stored_settings = store.load_settings()
    stored_observation = store.get_observation(today)
    assert stored_settings.setup_complete is True
    assert stored_settings.tracking_goal == TrackingGoal.AVOID_PREGNANCY
    assert stored_observation is not None
    assert stored_observation.temperature_unit == TemperatureUnit.FAHRENHEIT
    assert stored_observation.temperature_disturbances == [TemperatureDisturbance.POOR_SLEEP]
    assert stored_observation.fluid is not None
    assert stored_observation.fluid.sensation == FluidSensation.WATERY
    assert stored_observation.bleeding == BleedingLevel.MEDIUM
    assert result["today_interpretation"]["feedback"]["headline"] == "Fertility possible"


def test_write_endpoint_rejects_requests_without_desktop_header(desktop_server) -> None:
    base_url, _ = desktop_server
    request = Request(
        f"{base_url}/api/settings",
        data=b"{}",
        method="PUT",
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(HTTPError) as exc_info:
        urlopen(request, timeout=2)

    assert exc_info.value.code == 403


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=2) as response:
        return json.loads(response.read())


def _put_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="PUT",
        headers={
            "Content-Type": "application/json",
            "X-Symptothermal-Client": "desktop-web",
        },
    )
    with urlopen(request, timeout=2) as response:
        return json.loads(response.read())
