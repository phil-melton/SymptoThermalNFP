import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import List

from .models import AppSettings, DailyObservation
from .algorithm import evaluate_cycle
from .taxonomy import FertilityState, TemperatureUnit


def _celsius_to_fahrenheit(c: float) -> float:
    return (c * 9.0 / 5.0) + 32.0


def plot_cycle(
    cycle_days: List[DailyObservation],
    settings: AppSettings | None = None,
    save_path: str = None,
):
    if settings is None:
        settings = AppSettings()

    eval_result = evaluate_cycle(cycle_days, settings)

    n = len(cycle_days)
    days = list(range(1, n + 1))
    display_in_f = settings.temperature_unit == TemperatureUnit.FAHRENHEIT

    # Build display temperatures from the rule traces (already in Celsius)
    temps_display = []
    for trace in eval_result.day_traces:
        if trace.temp_celsius is None:
            temps_display.append(None)
        elif display_in_f:
            temps_display.append(_celsius_to_fahrenheit(trace.temp_celsius))
        else:
            temps_display.append(trace.temp_celsius)

    mucus_scores = [trace.mucus_level or 0 for trace in eval_result.day_traces]
    states = eval_result.states

    fig, (ax_temp, ax_mucus) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    color_map = {
        FertilityState.PRE_OV_INFERTILE: '#E0F7FA',
        FertilityState.FERTILE: '#FFF9C4',
        FertilityState.POST_OV_INFERTILE: '#E8F5E9',
    }
    label_map = {
        FertilityState.PRE_OV_INFERTILE: 'Menses / Early Infertile',
        FertilityState.FERTILE: 'Fertile Window',
        FertilityState.POST_OV_INFERTILE: 'Post-Ovulatory Infertile',
    }

    for i in range(n):
        ax_temp.axvspan(i + 0.5, i + 1.5, facecolor=color_map[states[i]], alpha=0.5)
        ax_mucus.axvspan(i + 0.5, i + 1.5, facecolor=color_map[states[i]], alpha=0.5)

    unit_label = "F" if display_in_f else "C"
    ax_temp.plot(days, temps_display, marker='o', linestyle='-', color='b', label=f'Temperature ({unit_label})')

    if eval_result.coverline_celsius is not None:
        coverline_display = (
            _celsius_to_fahrenheit(eval_result.coverline_celsius) if display_in_f
            else eval_result.coverline_celsius
        )
        ax_temp.axhline(y=coverline_display, color='r', linestyle='--', label=f'Coverline ({coverline_display:.2f}{unit_label})')

    if eval_result.t_shift_day is not None:
        idx = eval_result.t_shift_day - 1  # Convert 1-indexed to 0-indexed
        ax_temp.scatter([eval_result.t_shift_day], [temps_display[idx]], color='red', s=100, zorder=5, label='Temp Shift Day')

    ax_temp.set_ylabel(f'Temperature ({unit_label})')
    ax_temp.set_title('Symptothermal Cycle Chart')
    ax_temp.grid(True, axis='y', linestyle=':', alpha=0.7)

    ax_mucus.bar(days, mucus_scores, color='purple', alpha=0.6, label='Mucus Score')
    ax_mucus.set_yticks([0, 1, 2, 3, 4])
    ax_mucus.set_yticklabels(['0 (Dry)', '1 (Sticky)', '2 (Creamy)', '3 (Watery)', '4 (Slippery)'])

    if eval_result.peak_day is not None:
        idx = eval_result.peak_day - 1  # Convert 1-indexed to 0-indexed
        ax_mucus.scatter([eval_result.peak_day], [mucus_scores[idx] + 0.2], marker='v', color='red', s=100, label='Peak Day')

    ax_mucus.set_xlabel('Cycle Day')
    ax_mucus.set_ylabel('Mucus Score')
    ax_mucus.grid(True, axis='y', linestyle=':', alpha=0.7)

    state_patches = [mpatches.Patch(color=color_map[key], alpha=0.5, label=label_map[key]) for key in color_map]

    handles_temp, labels_temp = ax_temp.get_legend_handles_labels()
    handles_mucus, labels_mucus = ax_mucus.get_legend_handles_labels()

    fig.legend(handles_temp + handles_mucus + state_patches, labels_temp + labels_mucus + [p.get_label() for p in state_patches], loc='upper right', bbox_to_anchor=(0.95, 0.95))

    plt.xticks(days)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Chart saved to {save_path}")

    plt.show()
