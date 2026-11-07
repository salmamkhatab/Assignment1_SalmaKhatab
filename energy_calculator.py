"""Module 1 - Energy Consumption Calculator.

Defines the Room class (one room and its electrical load) and the RoomManager
class (add / list / search / update rooms, totals, CSV save and load).
"""

import csv
import os

# Tuples: fixed, ordered definitions that never change at run time.
CSV_FIELDS = ("room_id", "room_name", "building", "area_m2",
              "lighting_kw", "ac_kw", "equipment_kw", "hours_per_day")
POWER_FIELDS = ("lighting_kw", "ac_kw", "equipment_kw")
HOURS_RANGE = (0, 24)  # allowed operating hours per day (inclusive)


# ----------------------------------------------------------------------------
# Input validation (each function returns the cleaned value or raises ValueError)
# ----------------------------------------------------------------------------
def validate_area(value):
    """Room area must be a number greater than zero."""
    area = _to_float(value, "Area")
    if area <= 0:
        raise ValueError("Area must be greater than zero.")
    return area


def validate_power(value, label="Power"):
    """Power values (kW) must be numbers that are not negative."""
    power = _to_float(value, label)
    if power < 0:
        raise ValueError(f"{label} cannot be negative.")
    return power


def validate_hours(value):
    """Operating hours per day must be between 0 and 24."""
    hours = _to_float(value, "Operating hours")
    low, high = HOURS_RANGE  # tuple unpacking
    if not low <= hours <= high:
        raise ValueError(f"Operating hours must be between {low} and {high}.")
    return hours


def validate_text(value, label):
    """Text fields cannot be empty."""
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} cannot be empty.")
    return text


def _to_float(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None


# Dictionary: field name -> validator, so the menu can validate one field at a time.
FIELD_VALIDATORS = {
    "room_name": lambda v: validate_text(v, "Room name"),
    "building": lambda v: validate_text(v, "Building"),
    "area_m2": validate_area,
    "lighting_kw": lambda v: validate_power(v, "Lighting power"),
    "ac_kw": lambda v: validate_power(v, "Air-conditioning power"),
    "equipment_kw": lambda v: validate_power(v, "Equipment power"),
    "hours_per_day": validate_hours,
}


# ----------------------------------------------------------------------------
# Room class
# ----------------------------------------------------------------------------
class Room:
    """One room with its size, installed power (kW) and daily operating hours."""

    def __init__(self, room_id, room_name, building, area_m2,
                 lighting_kw, ac_kw, equipment_kw, hours_per_day):
        self.room_id = validate_text(room_id, "Room ID").upper()
        self.room_name = validate_text(room_name, "Room name")
        self.building = validate_text(building, "Building")
        self.area_m2 = validate_area(area_m2)
        self.lighting_kw = validate_power(lighting_kw, "Lighting power")
        self.ac_kw = validate_power(ac_kw, "Air-conditioning power")
        self.equipment_kw = validate_power(equipment_kw, "Equipment power")
        self.hours_per_day = validate_hours(hours_per_day)

    # --- calculations --------------------------------------------------------
    @property
    def total_power_kw(self):
        return self.lighting_kw + self.ac_kw + self.equipment_kw

    def daily_energy_kwh(self):
        """Daily energy (kWh) = total power (kW) x operating hours."""
        return self.total_power_kw * self.hours_per_day

    def energy_per_m2(self):
        """Consumption per square metre = daily energy / room area."""
        return self.daily_energy_kwh() / self.area_m2

    # --- helpers -------------------------------------------------------------
    def update(self, **changes):
        """Update fields with validation. Nothing changes if any value is invalid."""
        unknown = set(changes) - set(CSV_FIELDS[1:])  # set difference
        if unknown:
            raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
        candidate = self.to_dict()
        candidate.update(changes)
        checked = Room(**candidate)  # re-runs every validation rule
        for name in CSV_FIELDS[1:]:
            setattr(self, name, getattr(checked, name))

    def to_dict(self):
        return {name: getattr(self, name) for name in CSV_FIELDS}

    def __str__(self):
        return (f"{self.room_id:<4} {self.room_name:<15} {self.building:<15} "
                f"{self.area_m2:>6.1f} m2 | {self.total_power_kw:>5.1f} kW x "
                f"{self.hours_per_day:>4.1f} h = {self.daily_energy_kwh():>7.1f} kWh/day "
                f"({self.energy_per_m2():.2f} kWh/m2)")


# ----------------------------------------------------------------------------
# RoomManager class
# ----------------------------------------------------------------------------
class RoomManager:
    """Keeps a list of Room objects and provides add/list/search/update/save."""

    def __init__(self):
        self.rooms = []  # list of Room objects

    def add_room(self, room):
        if self.get_room(room.room_id) is not None:
            raise ValueError(f"Room ID {room.room_id} already exists.")
        self.rooms.append(room)

    def get_room(self, room_id):
        wanted = str(room_id).strip().upper()
        for room in self.rooms:
            if room.room_id == wanted:
                return room
        return None

    def list_rooms(self):
        return list(self.rooms)

    def search(self, keyword):
        """Case-insensitive search in room ID, name and building."""
        key = str(keyword).strip().lower()
        return [r for r in self.rooms
                if key in r.room_id.lower()
                or key in r.room_name.lower()
                or key in r.building.lower()]

    def update_room(self, room_id, **changes):
        room = self.get_room(room_id)
        if room is None:
            raise KeyError(f"Room {room_id} not found.")
        room.update(**changes)
        return room

    # --- totals --------------------------------------------------------------
    def total_daily_energy(self):
        return sum(r.daily_energy_kwh() for r in self.rooms)

    def buildings(self):
        return sorted({r.building for r in self.rooms})  # set -> unique buildings

    def energy_by_building(self):
        totals = {}  # dict: building -> kWh/day
        for r in self.rooms:
            totals[r.building] = totals.get(r.building, 0.0) + r.daily_energy_kwh()
        return totals

    def ranked_by_energy(self):
        """Rooms sorted from highest to lowest daily energy."""
        return sorted(self.rooms, key=lambda r: r.daily_energy_kwh(), reverse=True)

    def summary_text(self):
        """Per-room table, total, and consumption per m2 (uses indexing/slicing)."""
        if not self.rooms:
            return "No rooms yet."
        lines = [str(r) for r in self.rooms]
        total = self.total_daily_energy()
        total_area = sum(r.area_m2 for r in self.rooms)
        top3 = self.ranked_by_energy()[:3]  # slicing
        lines.append("-" * 60)
        lines.append(f"Total daily consumption : {total:,.1f} kWh")
        lines.append(f"Total area              : {total_area:,.1f} m2")
        lines.append(f"Overall per m2          : {total / total_area:.2f} kWh/m2/day")
        lines.append("Highest consumers       : " +
                     ", ".join(f"{r.room_name} ({r.daily_energy_kwh():.0f} kWh)" for r in top3))
        for building, kwh in self.energy_by_building().items():
            lines.append(f"  {building:<15}: {kwh:,.1f} kWh/day")
        return "\n".join(lines)

    # --- CSV -----------------------------------------------------------------
    def save_csv(self, path):
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for room in self.rooms:
                writer.writerow(room.to_dict())

    def load_csv(self, path):
        """Replace the current rooms with the rows of a CSV file.

        Invalid rows are skipped and reported; returns (loaded_count, errors).
        """
        loaded, errors = [], []
        with open(path, newline="", encoding="utf-8") as f:
            for line_no, row in enumerate(csv.DictReader(f), start=2):
                try:
                    loaded.append(Room(**{k: row[k] for k in CSV_FIELDS}))
                except (ValueError, KeyError) as err:
                    errors.append(f"line {line_no}: {err}")
        self.rooms = []
        for room in loaded:
            try:
                self.add_room(room)
            except ValueError as err:
                errors.append(str(err))
        return len(self.rooms), errors

    def to_dataframe(self):
        """Hand the room data to Module 2 (imported lazily so Module 1 stays pandas-free)."""
        import pandas as pd
        return pd.DataFrame([r.to_dict() for r in self.rooms], columns=list(CSV_FIELDS))
