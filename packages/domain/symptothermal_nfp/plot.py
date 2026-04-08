import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import List
from .models import DailyObservation
from .algorithm import evaluate_cycle, map_fluid_score, _celsius_to_fahrenheit

def plot_cycle(cycle_days: List[DailyObservation], save_path: str = None):
    eval_result = evaluate_cycle(cycle_days)

    n = len(cycle_days)
    days = list(range(1, n + 1))

    temps_f = []
    for day in cycle_days:
        if day.waking_temperature is None or day.temperature_disturbed:
            temps_f.append(None)
        else:
            if day.waking_temperature < 50:
                temps_f.append(_celsius_to_fahrenheit(day.waking_temperature))
            else:
                temps_f.append(day.waking_temperature)

    mucus_scores = [map_fluid_score(day.fluid) for day in cycle_days]
    states = eval_result.states

    fig, (ax_temp, ax_mucus) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Background colors
    color_map = {0: '#E0F7FA', 1: '#FFF9C4', 2: '#E8F5E9'}
    label_map = {0: 'Menses / Early Infertile', 1: 'Fertile Window', 2: 'Post-Ovulatory Infertile'}

    # Plot backgrounds for temperature axis
    for i in range(n):
        ax_temp.axvspan(i + 0.5, i + 1.5, facecolor=color_map[states[i]], alpha=0.5)
        ax_mucus.axvspan(i + 0.5, i + 1.5, facecolor=color_map[states[i]], alpha=0.5)

    # Plot temperatures
    ax_temp.plot(days, temps_f, marker='o', linestyle='-', color='b', label='Temperature (F)')

    if eval_result.t_cover is not None:
        ax_temp.axhline(y=eval_result.t_cover, color='r', linestyle='--', label=f'Coverline ({eval_result.t_cover:.2f}F)')

    if eval_result.t_shift is not None:
        ax_temp.scatter([eval_result.t_shift + 1], [temps_f[eval_result.t_shift]], color='red', s=100, zorder=5, label='Temp Shift Day')

    ax_temp.set_ylabel('Temperature (F)')
    ax_temp.set_title('Symptothermal Cycle Chart')
    ax_temp.grid(True, axis='y', linestyle=':', alpha=0.7)

    # Plot mucus scores
    ax_mucus.bar(days, mucus_scores, color='purple', alpha=0.6, label='Mucus Score')
    ax_mucus.set_yticks([0, 1, 2, 3, 4])
    ax_mucus.set_yticklabels(['0 (Dry)', '1 (Sticky)', '2 (Creamy)', '3 (Watery)', '4 (Slippery)'])

    if eval_result.t_peak is not None:
        ax_mucus.scatter([eval_result.t_peak + 1], [mucus_scores[eval_result.t_peak] + 0.2], marker='v', color='red', s=100, label='Peak Day')

    ax_mucus.set_xlabel('Cycle Day')
    ax_mucus.set_ylabel('Mucus Score')
    ax_mucus.grid(True, axis='y', linestyle=':', alpha=0.7)

    # Create legend for states
    state_patches = [mpatches.Patch(color=color_map[key], alpha=0.5, label=label_map[key]) for key in [0, 1, 2]]

    handles_temp, labels_temp = ax_temp.get_legend_handles_labels()
    handles_mucus, labels_mucus = ax_mucus.get_legend_handles_labels()

    fig.legend(handles_temp + handles_mucus + state_patches, labels_temp + labels_mucus + [p.get_label() for p in state_patches], loc='upper right', bbox_to_anchor=(0.95, 0.95))

    plt.xticks(days)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Chart saved to {save_path}")

    plt.show()
