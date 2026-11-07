"""Module 2 - Consumption and Cost Analysis.

Reads actual daily readings, cleans them with pandas, merges them with the room
data from Module 1, calculates consumption and cost per room / building / month,
compares estimated consumption before and after cutting air-conditioning power
(NumPy), draws four Matplotlib charts, and exports CSV reports and PNG charts.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

READING_COLUMNS = ("room_id", "date", "actual_kwh")
BUILDING_COLORS = {"Admin Block": "#1f77b4", "Academic Block": "#ff7f0e"}  # dict
HISTOGRAM_COLOR = "#2ca02c"


# ----------------------------------------------------------------------------
# Loading and cleaning
# ----------------------------------------------------------------------------
def load_readings(path):
    """Read the readings CSV and check that the expected columns exist."""
    df = pd.read_csv(path)
    missing_cols = set(READING_COLUMNS) - set(df.columns)  # set difference
    if missing_cols:
        raise ValueError(f"Readings file is missing column(s): {sorted(missing_cols)}")
    return df[list(READING_COLUMNS)].copy()


def clean_readings(df):
    """Clean raw readings. Returns (clean_df, report).

    Steps: tidy text and types -> drop unusable rows -> remove duplicates ->
    fill missing kWh by linear interpolation inside each room.
    """
    report = {"rows_raw": len(df)}
    df = df.copy()

    df["room_id"] = df["room_id"].astype(str).str.strip().str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["actual_kwh"] = pd.to_numeric(df["actual_kwh"], errors="coerce")

    bad = df["date"].isna() | df["room_id"].isin(["", "NAN"])
    report["invalid_rows_removed"] = int(bad.sum())
    df = df[~bad]

    negative = df["actual_kwh"] < 0  # a meter cannot read negative energy
    report["negative_values_set_missing"] = int(negative.sum())
    df.loc[negative, "actual_kwh"] = np.nan

    before = len(df)
    df = df.drop_duplicates(subset=["room_id", "date"], keep="first")
    report["duplicates_removed"] = before - len(df)

    df = df.sort_values(["room_id", "date"]).reset_index(drop=True)

    report["missing_before"] = int(df["actual_kwh"].isna().sum())
    df["was_missing"] = df["actual_kwh"].isna()
    df["actual_kwh"] = df.groupby("room_id")["actual_kwh"].transform(
        lambda s: s.interpolate(method="linear", limit_direction="both"))
    still_missing = df["actual_kwh"].isna()  # rooms with no readings at all
    report["rows_dropped_unfillable"] = int(still_missing.sum())
    df = df[~still_missing].reset_index(drop=True)
    report["missing_filled"] = int(df["was_missing"].sum())
    report["rows_clean"] = len(df)
    return df, report


def filled_rows(clean_df):
    """The rows whose value was filled in (for transparency in reports)."""
    return clean_df.loc[clean_df["was_missing"], ["room_id", "date", "actual_kwh"]]


# ----------------------------------------------------------------------------
# Merge, cost and grouped summaries
# ----------------------------------------------------------------------------
def merge_with_rooms(readings, rooms_df):
    """Attach room details to every reading. Returns (merged_df, unmatched_ids)."""
    unmatched = sorted(set(readings["room_id"]) - set(rooms_df["room_id"]))
    merged = readings.merge(rooms_df, on="room_id", how="inner", validate="many_to_one")
    merged["month"] = merged["date"].dt.strftime("%Y-%m")
    return merged, unmatched


def add_cost(merged, price_per_kwh):
    """cost = actual kWh x price per kWh."""
    if price_per_kwh < 0:
        raise ValueError("Price per kWh cannot be negative.")
    out = merged.copy()
    out["cost"] = out["actual_kwh"] * price_per_kwh
    return out


def _agg(df, keys):
    table = (df.groupby(keys)
               .agg(total_kwh=("actual_kwh", "sum"),
                    avg_daily_kwh=("actual_kwh", "mean"),
                    total_cost=("cost", "sum"))
               .round(2)
               .reset_index())
    return table


def build_tables(costed):
    """Return a dict of report tables: per room, building, month and combinations."""
    by_room = _agg(costed, ["room_id", "room_name", "building"])
    info = costed.groupby("room_id").agg(area_m2=("area_m2", "first"),
                                         lighting_kw=("lighting_kw", "first"),
                                         ac_kw=("ac_kw", "first"),
                                         equipment_kw=("equipment_kw", "first"),
                                         hours=("hours_per_day", "first"))
    est_daily = (info["lighting_kw"] + info["ac_kw"] + info["equipment_kw"]) * info["hours"]
    by_room = by_room.merge(est_daily.rename("estimated_daily_kwh").round(2),
                            left_on="room_id", right_index=True)
    by_room["actual_vs_estimated_pct"] = (
        by_room["avg_daily_kwh"] / by_room["estimated_daily_kwh"] * 100).round(1)
    by_room = by_room.merge(info["area_m2"], left_on="room_id", right_index=True)
    by_room["avg_kwh_per_m2_day"] = (by_room["avg_daily_kwh"] / by_room["area_m2"]).round(3)
    by_room = by_room.drop(columns="area_m2")

    return {
        "consumption_by_room": by_room,
        "consumption_by_building": _agg(costed, ["building"]),
        "consumption_by_month": _agg(costed, ["month"]),
        "consumption_by_building_month": _agg(costed, ["building", "month"]),
        "consumption_by_room_month": _agg(costed, ["room_id", "room_name", "month"]),
    }


# ----------------------------------------------------------------------------
# NumPy scenario: reduce air-conditioning power
# ----------------------------------------------------------------------------
def ac_reduction_scenario(rooms_df, reduction_pct, price_per_kwh, days=30):
    """Estimated daily kWh before/after cutting AC power by reduction_pct (%).

    Operating hours and lighting/equipment power stay unchanged.
    """
    if not 0 <= reduction_pct <= 100:
        raise ValueError("Reduction must be between 0 and 100 percent.")
    if price_per_kwh < 0:
        raise ValueError("Price per kWh cannot be negative.")

    lighting = rooms_df["lighting_kw"].to_numpy(dtype=float)
    ac = rooms_df["ac_kw"].to_numpy(dtype=float)
    equipment = rooms_df["equipment_kw"].to_numpy(dtype=float)
    hours = rooms_df["hours_per_day"].to_numpy(dtype=float)

    before = (lighting + ac + equipment) * hours
    ac_after = ac * (1 - reduction_pct / 100)
    after = (lighting + ac_after + equipment) * hours
    saving = before - after
    saving_pct = np.divide(saving, before, out=np.zeros_like(saving), where=before > 0) * 100

    result = rooms_df[["room_id", "room_name", "building"]].copy()
    result["ac_kw_before"] = ac
    result["ac_kw_after"] = ac_after.round(3)
    result["before_kwh_day"] = before.round(2)
    result["after_kwh_day"] = after.round(2)
    result["saving_kwh_day"] = saving.round(2)
    result["saving_pct"] = saving_pct.round(2)
    result[f"saving_kwh_{days}d"] = (saving * days).round(2)
    result[f"cost_saving_{days}d"] = (saving * days * price_per_kwh).round(2)
    return result


def scenario_totals(scenario_df, days=30):
    """Totals for the scenario table as a tuple: (before, after, saving, saving %)."""
    before = float(scenario_df["before_kwh_day"].sum())
    after = float(scenario_df["after_kwh_day"].sum())
    saving = before - after
    pct = saving / before * 100 if before else 0.0
    return before, after, saving, pct


# ----------------------------------------------------------------------------
# Charts (each function returns a Matplotlib figure)
# ----------------------------------------------------------------------------
def _period_label(costed):
    start, end = costed["date"].min(), costed["date"].max()
    return f"{start:%d %b %Y} - {end:%d %b %Y}"


def plot_line(costed):
    """Line chart: daily energy per building."""
    daily = costed.pivot_table(index="date", columns="building",
                               values="actual_kwh", aggfunc="sum")
    fig, ax = plt.subplots(figsize=(10, 5))
    for building in daily.columns:
        ax.plot(daily.index, daily[building], label=building,
                color=BUILDING_COLORS.get(building), linewidth=1.8)
    ax.set_title(f"Daily Energy Consumption by Building ({_period_label(costed)})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Energy consumption (kWh per day)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_bar(costed, price_per_kwh):
    """Bar chart: total cost per room."""
    cost = (costed.groupby(["room_id", "room_name", "building"])["cost"]
                  .sum().reset_index())
    labels = [f"{rid}\n{name}" for rid, name in zip(cost["room_id"], cost["room_name"])]
    colors = [BUILDING_COLORS.get(b, "gray") for b in cost["building"]]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, cost["cost"], color=colors)
    ax.bar_label(bars, fmt="%.0f", padding=2, fontsize=8)
    ax.set_title(f"Total Energy Cost per Room at {price_per_kwh:g} per kWh "
                 f"({_period_label(costed)})")
    ax.set_xlabel("Room")
    ax.set_ylabel("Total cost (currency units)")
    ax.grid(axis="y", alpha=0.3)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in BUILDING_COLORS.values()]
    ax.legend(handles, BUILDING_COLORS.keys())
    fig.tight_layout()
    return fig


def plot_scatter(costed):
    """Scatter chart: room area vs average daily consumption."""
    stats = costed.groupby(["room_id", "building"]).agg(
        area=("area_m2", "first"), avg_kwh=("actual_kwh", "mean")).reset_index()
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for building, part in stats.groupby("building"):
        ax.scatter(part["area"], part["avg_kwh"], s=90, label=building,
                   color=BUILDING_COLORS.get(building))
        for _, row in part.iterrows():
            ax.annotate(row["room_id"], (row["area"], row["avg_kwh"]),
                        textcoords="offset points", xytext=(6, 5), fontsize=9)
    ax.set_title("Room Area vs Average Daily Energy Consumption")
    ax.set_xlabel("Room area (m\u00b2)")
    ax.set_ylabel("Average daily consumption (kWh per day)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_histogram(costed):
    """Histogram: distribution of all daily readings."""
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(costed["actual_kwh"], bins=20, color=HISTOGRAM_COLOR, edgecolor="white")
    ax.set_title("Distribution of Daily Energy Readings (all rooms)")
    ax.set_xlabel("Daily energy consumption (kWh)")
    ax.set_ylabel("Number of room-days (count)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def save_charts(costed, price_per_kwh, out_dir):
    """Draw all four charts and save them as PNG files. Returns the file paths."""
    os.makedirs(out_dir, exist_ok=True)
    figures = (("line_daily_energy_by_building.png", plot_line(costed)),
               ("bar_cost_per_room.png", plot_bar(costed, price_per_kwh)),
               ("scatter_area_vs_consumption.png", plot_scatter(costed)),
               ("histogram_daily_readings.png", plot_histogram(costed)))
    paths = []
    for filename, fig in figures:  # tuple unpacking in a loop
        path = os.path.join(out_dir, filename)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths


# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------
def export_reports(tables, out_dir):
    """Write every DataFrame in the dict `tables` to out_dir as CSV. Returns paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, table in tables.items():
        path = os.path.join(out_dir, f"{name}.csv")
        table.to_csv(path, index=False)
        paths.append(path)
    return paths


# ----------------------------------------------------------------------------
# Session object used by the menu in main.py
# ----------------------------------------------------------------------------
class ConsumptionAnalysis:
    """Keeps the cleaned readings and builds merged / costed data on demand."""

    def __init__(self):
        self.clean = None          # cleaned readings DataFrame
        self.report = None         # dict describing the cleaning steps
        self.price = None          # price per kWh
        self.scenario = None       # last AC-reduction table
        self.scenario_pct = None

    def load(self, path):
        raw = load_readings(path)
        self.clean, self.report = clean_readings(raw)
        return self.report

    def costed(self, rooms_df, price_per_kwh):
        """Merge readings with the current room data and add cost."""
        if self.clean is None:
            raise RuntimeError("Load the readings first.")
        merged, unmatched = merge_with_rooms(self.clean, rooms_df)
        if merged.empty:
            raise RuntimeError("No readings match the room IDs in the room list.")
        self.price = price_per_kwh
        return add_cost(merged, price_per_kwh), unmatched
