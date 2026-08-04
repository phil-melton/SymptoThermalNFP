from __future__ import annotations

from typing import Iterable

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from .interpretation import UserFertilityLabel, evaluate_observations
from .models import AppSettings, DailyObservation
from .taxonomy import FluidSensation, TemperatureUnit


def plot_cycle(
    cycle_days: Iterable[DailyObservation],
    save_path: str | None = None,
    settings: AppSettings | None = None,
) -> None:
    """Plot a cycle using the canonical stm-v1 interpretation result."""

    days_data = sorted(cycle_days, key=lambda item: item.observation_date)
    if not days_data:
        raise ValueError("At least one observation is required to plot a cycle.")

    active_settings = settings or AppSettings()
    report = evaluate_observations(days_data, active_settings)
    cycle = report.cycles[-1]
    interpretations = {item.observation_date: item for item in cycle.days}
    display_unit = active_settings.temperature_unit
    day_numbers = list(range(1, len(days_data) + 1))

    temperatures = [
        _display_temperature(item, display_unit, active_settings)
        for item in days_data
    ]
    mucus_scores = [_mucus_score(item) for item in days_data]

    figure, (temperature_axis, mucus_axis) = plt.subplots(
        2,
        1,
        figsize=(10, 8),
        sharex=True,
    )

    colors = {
        UserFertilityLabel.FERTILITY_POSSIBLE: "#FFF0C7",
        UserFertilityLabel.NOT_ENOUGH_INFORMATION: "#E7E9ED",
        UserFertilityLabel.LOWER_PROBABILITY_METHOD_RULES_APPLY: "#DDEBF7",
        UserFertilityLabel.POST_OVULATION_CONFIRMED: "#DDF3E4",
    }
    labels = {
        UserFertilityLabel.FERTILITY_POSSIBLE: "Fertility possible",
        UserFertilityLabel.NOT_ENOUGH_INFORMATION: "Not enough information",
        UserFertilityLabel.LOWER_PROBABILITY_METHOD_RULES_APPLY: "Lower probability — method rules apply",
        UserFertilityLabel.POST_OVULATION_CONFIRMED: "Post-ovulation confirmed",
    }

    used_labels: set[UserFertilityLabel] = set()
    for index, observation in enumerate(days_data, start=1):
        interpretation = interpretations[observation.observation_date]
        label = interpretation.feedback.label if interpretation.feedback else UserFertilityLabel.NOT_ENOUGH_INFORMATION
        used_labels.add(label)
        for axis in (temperature_axis, mucus_axis):
            axis.axvspan(index - 0.5, index + 0.5, facecolor=colors[label], alpha=0.75)

    temperature_axis.plot(
        day_numbers,
        temperatures,
        marker="o",
        linestyle="-",
        color="#183C40",
        label=f"Temperature (°{'F' if display_unit == TemperatureUnit.FAHRENHEIT else 'C'})",
    )

    if cycle.temperature_shift:
        coverline = cycle.temperature_shift.coverline_celsius
        if display_unit == TemperatureUnit.FAHRENHEIT:
            coverline = _celsius_to_fahrenheit(coverline)
        temperature_axis.axhline(
            y=coverline,
            color="#A84A3A",
            linestyle="--",
            label=f"Coverline ({coverline:.2f}°{'F' if display_unit == TemperatureUnit.FAHRENHEIT else 'C'})",
        )

    temperature_axis.set_ylabel("Waking temperature")
    temperature_axis.set_title("Symptothermal cycle chart")
    temperature_axis.grid(True, axis="y", linestyle=":", alpha=0.5)

    mucus_axis.bar(day_numbers, mucus_scores, color="#7A5C91", alpha=0.75, label="Mucus sign")
    mucus_axis.set_yticks([0, 1, 2, 3, 4])
    mucus_axis.set_yticklabels(["Dry", "Sticky", "Creamy", "Wet", "Slippery"])
    mucus_axis.set_xlabel("Cycle day")
    mucus_axis.set_ylabel("Most fertile sign")
    mucus_axis.grid(True, axis="y", linestyle=":", alpha=0.5)

    status_patches = [
        mpatches.Patch(color=colors[label], label=labels[label])
        for label in colors
        if label in used_labels
    ]
    handles_temperature, labels_temperature = temperature_axis.get_legend_handles_labels()
    handles_mucus, labels_mucus = mucus_axis.get_legend_handles_labels()
    figure.legend(
        handles_temperature + handles_mucus + status_patches,
        labels_temperature + labels_mucus + [patch.get_label() for patch in status_patches],
        loc="upper right",
        bbox_to_anchor=(0.98, 0.98),
    )

    plt.xticks(day_numbers)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Chart saved to {save_path}")

    plt.show()


def _display_temperature(
    observation: DailyObservation,
    display_unit: TemperatureUnit,
    settings: AppSettings,
) -> float | None:
    if observation.waking_temperature is None or observation.temperature_disturbed:
        return None

    source_unit = observation.temperature_unit or settings.temperature_unit
    value = observation.waking_temperature
    if source_unit == display_unit:
        return value
    if source_unit == TemperatureUnit.CELSIUS:
        return _celsius_to_fahrenheit(value)
    return (value - 32.0) * 5.0 / 9.0


def _mucus_score(observation: DailyObservation) -> int:
    if observation.fluid is None:
        return 0
    return {
        FluidSensation.DRY: 0,
        FluidSensation.STICKY: 1,
        FluidSensation.CREAMY: 2,
        FluidSensation.WATERY: 3,
        FluidSensation.SLIPPERY: 4,
    }[observation.fluid.sensation]


def _celsius_to_fahrenheit(value: float) -> float:
    return (value * 9.0 / 5.0) + 32.0
