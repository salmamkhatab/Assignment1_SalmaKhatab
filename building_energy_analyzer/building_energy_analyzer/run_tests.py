"""Runs 3 valid and 3 invalid test cases and records expected vs actual results.

Usage:  python run_tests.py      (writes reports/test_results.csv)
"""

import os

import pandas as pd

import cost_analysis as ca
from energy_calculator import Room

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_ROOM = dict(room_id="R01", room_name="Open Office", building="Admin Block",
                   area_m2=120, lighting_kw=1.8, ac_kw=9, equipment_kw=3.5, hours_per_day=10)


def invalid_room(**override):
    """Try to build a room with one bad value; return the error message (or 'no error')."""
    try:
        Room(**{**SAMPLE_ROOM, **override})
    except ValueError as err:
        return f"ValueError: {err}"
    return "no error"


def valid_energy_calculation():
    room = Room(**SAMPLE_ROOM)
    return (f"total power {room.total_power_kw:.1f} kW, daily {room.daily_energy_kwh():.1f} kWh, "
            f"{room.energy_per_m2():.2f} kWh/m2")


def valid_ac_reduction():
    rooms = pd.read_csv(os.path.join(BASE_DIR, "data", "rooms.csv"))
    result = ca.ac_reduction_scenario(rooms, 20, 1.5)
    r01 = result.loc[result["room_id"] == "R01"].iloc[0]
    _, _, total_saving, _ = ca.scenario_totals(result)
    return (f"R01 {r01['before_kwh_day']:.1f} -> {r01['after_kwh_day']:.1f} kWh/day; "
            f"all rooms save {total_saving:.2f} kWh/day")


def valid_cleaning():
    raw = ca.load_readings(os.path.join(BASE_DIR, "data", "readings.csv"))
    clean, report = ca.clean_readings(raw)
    return (f"{report['rows_clean']} rows, {report['duplicates_removed']} duplicates removed, "
            f"{report['missing_filled']} missing filled, {int(clean['actual_kwh'].isna().sum())} missing left")


# (id, kind, description, expected, function)
CASES = [
    ("V1", "valid", "Energy for R01 (1.8+9+3.5 kW, 10 h, 120 m2)",
     "total power 14.3 kW, daily 143.0 kWh, 1.19 kWh/m2", valid_energy_calculation),
    ("V2", "valid", "Cut AC power by 20% (hours and other loads unchanged)",
     "R01 143.0 -> 125.0 kWh/day; all rooms save 118.88 kWh/day", valid_ac_reduction),
    ("V3", "valid", "Clean readings.csv (490 raw rows)",
     "488 rows, 2 duplicates removed, 3 missing filled, 0 missing left", valid_cleaning),
    ("I1", "invalid", "Room area = 0", "ValueError: Area must be greater than zero.",
     lambda: invalid_room(area_m2=0)),
    ("I2", "invalid", "Air-conditioning power = -5 kW",
     "ValueError: Air-conditioning power cannot be negative.", lambda: invalid_room(ac_kw=-5)),
    ("I3", "invalid", "Operating hours = 25",
     "ValueError: Operating hours must be between 0 and 24.", lambda: invalid_room(hours_per_day=25)),
]


def main():
    rows = []
    for case_id, kind, description, expected, func in CASES:
        actual = func()
        rows.append({"id": case_id, "type": kind, "test": description, "expected": expected,
                     "actual": actual, "result": "PASS" if actual == expected else "FAIL"})
    results = pd.DataFrame(rows)
    for row in rows:
        print(f"[{row['result']}] {row['id']} {row['test']}\n       expected: {row['expected']}\n"
              f"       actual:   {row['actual']}")
    os.makedirs(os.path.join(BASE_DIR, "reports"), exist_ok=True)
    results.to_csv(os.path.join(BASE_DIR, "reports", "test_results.csv"), index=False)
    passed = (results["result"] == "PASS").sum()
    print(f"\n{passed}/{len(results)} tests passed. Saved reports/test_results.csv")


if __name__ == "__main__":
    main()
