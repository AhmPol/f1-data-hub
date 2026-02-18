TAB_NAMES_BASE = ["Overview", "Lap Times", "Telemetry", "Strategy", "Race", "Advanced"]

EXPLAINERS = {
    "show_driver_consistency": "Lower = more consistent. Std dev of quick-lap times.",
    "show_overall_laptimes": "Lap time vs lap number for selected drivers (faster = higher).",
    "show_all_laptimes": "Lap time distribution by driver (violin + box), sorted by median pace.",
    "show_lap_scatter": "Single-driver lap times colored by tyre compound (stints + pace).",
    "show_qualifying_results": "Driver fastest lap gap to pole (qualifying baseline).",
    "show_team_avg": "Team average fastest-lap gap to pole (car baseline).",
    "show_speed_comparison": "2 drivers: speed vs distance with corner markers (fastest laps).",
    "show_speed_diff_track": "2 drivers: speed delta painted on track map (where time is gained/lost).",
    "show_gear_visualizer": "Fastest lap track map colored by gear.",
    "show_stint_strategy": "Stint timeline by compound (strategy overview).",
    "show_tyre_degradation": "Lap time evolution within stints (tyre drop-off).",
    "show_race_results": "Positions over laps (race story / overtakes).",
    "show_sector_times": "Sector distributions (advanced; can look busy).",
    "show_telemetry_overlay": "Telemetry overlay (advanced; can be noisy/data-dependent).",
    "show_point_finishers": "Top 10 lap times over race (advanced; niche).",
}

FUNC_GROUP = {
    "show_driver_consistency": "Overview",
    "show_qualifying_results": "Overview",
    "show_team_avg": "Overview",

    "show_overall_laptimes": "Lap Times",
    "show_all_laptimes": "Lap Times",
    "show_lap_scatter": "Lap Times",

    "show_speed_comparison": "Telemetry",
    "show_speed_diff_track": "Telemetry",
    "show_gear_visualizer": "Telemetry",

    "show_stint_strategy": "Strategy",
    "show_tyre_degradation": "Strategy",

    "show_race_results": "Race",

    "show_sector_times": "Advanced",
    "show_telemetry_overlay": "Advanced",
    "show_point_finishers": "Advanced",
}

MODULE_ALLOWLIST = {
    "Race": {
        "show_driver_consistency",
        "show_qualifying_results", "show_team_avg",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_race_results",
        "show_sector_times", "show_telemetry_overlay", "show_point_finishers",
    },
    "Qualifying": {
        "show_driver_consistency",
        "show_qualifying_results", "show_team_avg",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_sector_times", "show_telemetry_overlay",
    },
    "Practice": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_sector_times", "show_telemetry_overlay",
    },
    "Testing": {
        "show_driver_consistency",
        "show_overall_laptimes", "show_all_laptimes", "show_lap_scatter",
        "show_speed_comparison", "show_speed_diff_track", "show_gear_visualizer",
        "show_stint_strategy", "show_tyre_degradation",
        "show_sector_times", "show_telemetry_overlay",
    },
}

COMPARE_FUNCS = [
    "show_speed_comparison",
    "show_speed_diff_track",
    "show_telemetry_overlay",
    "show_sector_times",
]

