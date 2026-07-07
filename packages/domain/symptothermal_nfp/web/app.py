from __future__ import annotations

import io
import os
import secrets
from datetime import date
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from ..excel_store import ExcelStore, ExcelStoreError, build_workbook
from ..interpretation import evaluate_observations
from ..models import (
    AppSettings,
    CervicalPositionObservation,
    DailyObservation,
    FluidObservation,
    parse_hhmm_time,
    parse_iso_date,
)
from ..taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixHeight,
    CervixOpening,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    RuleContext,
    TemperatureUnit,
)

DEFAULT_DATA_FILE = "data/symptothermal.xlsx"

STATUS_LABELS = {
    "relative_infertility": "Relatively infertile (Phase 1)",
    "potentially_fertile": "Potentially fertile",
    "absolute_infertility_from_evening": "Infertile from this evening",
    "absolute_infertility": "Infertile (Phase 3)",
    "basic_infertile_pattern_alternate_evening": "BIP: alternate evening",
}


def create_app(data_path: str | Path | None = None) -> Flask:
    app = Flask(__name__)
    # A random per-process key by default (sessions only hold flashes and the
    # CSRF token, so losing them on restart is harmless). Set
    # SYMPTOTHERMAL_SECRET for a stable key across restarts.
    app.config["SECRET_KEY"] = os.environ.get("SYMPTOTHERMAL_SECRET") or secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # uploads are small workbooks

    resolved = Path(
        data_path
        or os.environ.get("SYMPTOTHERMAL_XLSX", DEFAULT_DATA_FILE)
    )
    app.config["DATA_PATH"] = resolved
    store = ExcelStore(resolved)
    store.initialize()

    def csrf_token() -> str:
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_hex(16)
            session["csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if request.method != "POST":
            return
        expected = session.get("csrf_token")
        provided = request.form.get("csrf_token")
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            abort(400, description="Invalid or missing CSRF token; reload the page and try again.")

    def load_state():
        observations = store.load_observations()
        settings = store.load_settings()
        report = evaluate_observations(observations, settings)
        return observations, settings, report

    @app.get("/")
    def index():
        try:
            observations, settings, report = load_state()
        except ExcelStoreError as exc:
            flash(str(exc), "error")
            observations, settings = [], AppSettings()
            report = evaluate_observations([], settings)

        report_dict = report.as_dict()
        today_info = _today_summary(report_dict)
        chart = _chart_payload(observations, report_dict, settings)
        day_status = {
            day["observation_date"]: day["status"]
            for cycle in report_dict.get("cycles", [])
            for day in cycle.get("days", [])
        }
        observations_list = sorted(observations, key=lambda item: item.observation_date, reverse=True)
        return render_template(
            "index.html",
            observations=observations_list,
            observations_json=[item.as_dict() for item in observations_list],
            settings=settings,
            report=report_dict,
            today_info=today_info,
            chart=chart,
            day_status=day_status,
            status_labels=STATUS_LABELS,
            today=date.today().isoformat(),
            taxonomy={
                "sensations": [item.value for item in FluidSensation],
                "quantities": [item.value for item in FluidQuantity],
                "colors": [item.value for item in MucusColor],
                "textures": [item.value for item in MucusTexture],
                "bleeding": [item.value for item in BleedingLevel],
                "heights": [item.value for item in CervixHeight],
                "firmness": [item.value for item in CervixFirmness],
                "openings": [item.value for item in CervixOpening],
                "units": [item.value for item in TemperatureUnit],
                "rule_contexts": [item.value for item in RuleContext],
            },
        )

    @app.post("/observations")
    def add_observation():
        try:
            observation = _observation_from_form(request.form)
        except ValueError as exc:
            flash(f"Could not save observation: {exc}", "error")
            return redirect(url_for("index"))

        replaced = store.upsert_observation(observation)
        verb = "Updated" if replaced else "Logged"
        flash(f"{verb} observation for {observation.observation_date.isoformat()}.", "success")
        return redirect(url_for("index"))

    @app.post("/observations/<observation_date>/delete")
    def delete_observation(observation_date: str):
        try:
            parsed = parse_iso_date(observation_date)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("index"))
        if store.delete_observation(parsed):
            flash(f"Deleted observation for {observation_date}.", "success")
        else:
            flash(f"No observation found for {observation_date}.", "error")
        return redirect(url_for("index"))

    @app.post("/settings")
    def update_settings():
        form = request.form
        try:
            settings = AppSettings.from_dict(
                {
                    "temperature_unit": form.get("temperature_unit", "celsius"),
                    "default_wake_time": form.get("default_wake_time", "06:30"),
                    "track_cervical_position": form.get("track_cervical_position") == "on",
                    "rule_context": form.get("rule_context", "standard"),
                    "transition_cycle_count": int(form.get("transition_cycle_count") or 0),
                    "use_doering_rule": form.get("use_doering_rule") == "on",
                    "use_rotzer_rule": form.get("use_rotzer_rule") == "on",
                    "bip_enabled": form.get("bip_enabled") == "on",
                }
            )
        except ValueError as exc:
            flash(f"Could not save settings: {exc}", "error")
            return redirect(url_for("index"))
        store.save_settings(settings)
        flash("Settings saved.", "success")
        return redirect(url_for("index"))

    @app.post("/upload")
    def upload_excel():
        uploaded = request.files.get("workbook")
        if uploaded is None or not uploaded.filename:
            flash("Choose an .xlsx file to upload.", "error")
            return redirect(url_for("index"))

        mode = request.form.get("mode", "merge")
        try:
            result = store.import_workbook(uploaded.stream.read(), mode=mode)
        except (ExcelStoreError, ValueError) as exc:
            flash(f"Import failed: {exc}", "error")
            return redirect(url_for("index"))

        message = f"Imported {result.imported} observation(s)"
        if result.replaced:
            message += f" ({result.replaced} replaced existing days)"
        if result.settings_imported:
            message += "; settings sheet applied"
        message += "."
        flash(message, "success")
        for error in result.errors:
            flash(f"Skipped row {error.row}: {error.message}", "error")
        return redirect(url_for("index"))

    @app.get("/download")
    def download_excel():
        return send_file(
            io.BytesIO(store.export_bytes()),
            as_attachment=True,
            download_name="symptothermal-data.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/template.xlsx")
    def download_template():
        buffer = io.BytesIO()
        build_workbook([], store.load_settings()).save(buffer)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="symptothermal-template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/api/interpretation")
    def api_interpretation():
        try:
            _, _, report = load_state()
        except ExcelStoreError as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify(report.as_dict())

    @app.get("/api/observations")
    def api_observations():
        try:
            observations = store.load_observations()
        except ExcelStoreError as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify([item.as_dict() for item in observations])

    return app


def _observation_from_form(form) -> DailyObservation:
    date_value = (form.get("date") or "").strip()
    if not date_value:
        raise ValueError("Date is required.")
    observation_date = parse_iso_date(date_value)

    temperature_raw = (form.get("temperature") or "").strip()
    temperature = None
    if temperature_raw:
        try:
            temperature = float(temperature_raw)
        except ValueError as exc:
            raise ValueError(f"Temperature {temperature_raw!r} is not a number.") from exc

    unit_raw = (form.get("temperature_unit") or "").strip()
    temperature_unit = TemperatureUnit(unit_raw) if unit_raw else None

    time_raw = (form.get("temperature_time") or "").strip()
    temperature_time = parse_hhmm_time(time_raw) if time_raw else None

    fluid = None
    sensation_raw = (form.get("fluid_sensation") or "").strip()
    if sensation_raw:
        amount_raw = (form.get("fluid_amount") or "").strip()
        fluid = FluidObservation(
            sensation=FluidSensation(sensation_raw),
            quantity=FluidQuantity(form.get("fluid_quantity") or "none"),
            color=MucusColor(form.get("fluid_color") or "none"),
            texture=MucusTexture(form.get("fluid_texture") or "none"),
            amount=int(amount_raw) if amount_raw else None,
            peak_quality=form.get("peak_quality") == "on",
        )

    cervix = None
    height_raw = (form.get("cervix_height") or "").strip()
    firmness_raw = (form.get("cervix_firmness") or "").strip()
    opening_raw = (form.get("cervix_opening") or "").strip()
    if height_raw or firmness_raw or opening_raw:
        if not (height_raw and firmness_raw and opening_raw):
            raise ValueError("Cervix observation needs height, firmness, and opening together.")
        cervix = CervicalPositionObservation(
            height=CervixHeight(height_raw),
            firmness=CervixFirmness(firmness_raw),
            opening=CervixOpening(opening_raw),
        )

    return DailyObservation(
        observation_date=observation_date,
        waking_temperature=temperature,
        temperature_unit=temperature_unit,
        temperature_time=temperature_time,
        temperature_disturbed=form.get("temperature_disturbed") == "on",
        fluid=fluid,
        cervical_position=cervix,
        bleeding=BleedingLevel(form.get("bleeding") or "none"),
        notes=(form.get("notes") or "").strip(),
    )


def _today_summary(report_dict: dict) -> dict | None:
    """Return the most recent daily interpretation across all cycles."""
    latest = None
    for cycle in report_dict.get("cycles", []):
        for day in cycle.get("days", []):
            if latest is None or day["observation_date"] > latest["observation_date"]:
                latest = dict(day)
                latest["cycle_index"] = cycle["cycle_index"]
    return latest


def _chart_payload(observations, report_dict: dict, settings: AppSettings) -> dict:
    """Build the per-cycle chart data consumed by the front-end SVG renderer."""
    status_by_date: dict[str, str] = {}
    cycles_meta = []
    for cycle in report_dict.get("cycles", []):
        for day in cycle.get("days", []):
            status_by_date[day["observation_date"]] = day["status"]
        shift = cycle.get("temperature_shift") or {}
        cycles_meta.append(
            {
                "cycle_index": cycle["cycle_index"],
                "start_date": cycle["start_date"],
                "end_date": cycle["end_date"],
                "peak_day": cycle.get("peak_day"),
                "coverline": shift.get("coverline_celsius"),
                "first_high_date": shift.get("first_high_date"),
                "absolute_start": cycle.get("absolute_infertility_start_date"),
                "fertile_window_start": cycle.get("fertile_window_start_date"),
            }
        )

    points = []
    for observation in sorted(observations, key=lambda item: item.observation_date):
        temp_c = None
        if observation.waking_temperature is not None:
            unit = observation.temperature_unit or settings.temperature_unit
            temp_c = (
                (observation.waking_temperature - 32.0) * 5.0 / 9.0
                if unit == TemperatureUnit.FAHRENHEIT
                else observation.waking_temperature
            )
        iso = observation.observation_date.isoformat()
        points.append(
            {
                "date": iso,
                "temp_c": round(temp_c, 3) if temp_c is not None else None,
                "disturbed": observation.temperature_disturbed,
                "bleeding": observation.bleeding.value,
                "mucus": observation.fluid.sensation.value if observation.fluid else None,
                "peak_quality": bool(observation.fluid and observation.fluid.peak_quality),
                "status": status_by_date.get(iso),
            }
        )

    return {"points": points, "cycles": cycles_meta}


def main() -> None:
    """Console entry point: run the local web UI."""
    app = create_app()
    host = os.environ.get("SYMPTOTHERMAL_HOST", "127.0.0.1")
    port = int(os.environ.get("SYMPTOTHERMAL_PORT", "5000"))
    print(f"SymptoThermalNFP web UI on http://{host}:{port} (data: {app.config['DATA_PATH']})")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
