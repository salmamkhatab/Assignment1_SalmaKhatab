"""Building Energy Analyzer - menu that connects Module 1 and Module 2."""

import os

import matplotlib

matplotlib.use("Agg")  # the menu only saves PNG files, so no chart window is needed

import cost_analysis as ca
from energy_calculator import FIELD_VALIDATORS, Room, RoomManager, validate_text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOMS_CSV = os.path.join(BASE_DIR, "data", "rooms.csv")
READINGS_CSV = os.path.join(BASE_DIR, "data", "readings.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")

MENU = """
=========== BUILDING ENERGY ANALYZER ===========
 Module 1 - Energy calculator
  1. Add a room
  2. List rooms
  3. Search rooms
  4. Update a room
  5. Energy summary (kWh/day, total, kWh/m2)
  6. Save rooms to CSV
 Module 2 - Consumption and cost analysis
  7. Load and clean readings CSV
  8. Cost report (room / building / month)
  9. Air-conditioning reduction scenario
 10. Create charts (PNG)
 11. Export reports (CSV)
  0. Exit
================================================"""


# ----------------------------------------------------------------------------
# Input helpers
# ----------------------------------------------------------------------------
def ask(prompt, validator, default=None):
    """Keep asking until validator accepts the answer. Enter keeps `default`."""
    while True:
        text = input(prompt).strip()
        if text == "" and default is not None:
            return default
        try:
            return validator(text)
        except ValueError as err:
            print(f"  Invalid input: {err}")


def ask_price(current=None):
    def check(text):
        value = float(text) if text.replace(".", "", 1).isdigit() else None
        if value is None:
            raise ValueError("Price must be a non-negative number.")
        return value
    suffix = f" [{current:g}]" if current is not None else ""
    return ask(f"Price per kWh{suffix}: ", check, default=current)


def ask_percent():
    def check(text):
        try:
            value = float(text)
        except ValueError:
            raise ValueError("Enter a number between 0 and 100.") from None
        if not 0 <= value <= 100:
            raise ValueError("Reduction must be between 0 and 100 percent.")
        return value
    return ask("Reduce air-conditioning power by (%): ", check)


# ----------------------------------------------------------------------------
# Module 1 actions
# ----------------------------------------------------------------------------
def add_room(manager):
    print("\n-- Add a room --")
    while True:
        room_id = ask("Room ID (e.g. R09): ", lambda v: validate_text(v, "Room ID"))
        if manager.get_room(room_id) is None:
            break
        print(f"  Room {room_id.upper()} already exists.")
    prompts = (("room_name", "Room name: "), ("building", "Building: "),
               ("area_m2", "Area (m2): "), ("lighting_kw", "Lighting power (kW): "),
               ("ac_kw", "Air-conditioning power (kW): "),
               ("equipment_kw", "Equipment power (kW): "),
               ("hours_per_day", "Operating hours per day (0-24): "))
    values = {field: ask(text, FIELD_VALIDATORS[field]) for field, text in prompts}
    room = Room(room_id, **values)
    manager.add_room(room)
    print(f"Added: {room}")


def list_rooms(manager):
    rooms = manager.list_rooms()
    if not rooms:
        print("No rooms yet.")
    for room in rooms:
        print(room)


def search_rooms(manager):
    keyword = input("Search (room ID, name or building): ")
    found = manager.search(keyword)
    print(f"{len(found)} room(s) found.")
    for room in found:
        print(room)


def update_room(manager):
    room_id = input("Room ID to update: ")
    room = manager.get_room(room_id)
    if room is None:
        print("Room not found.")
        return
    print(f"Current: {room}")
    print("Press Enter to keep the current value.")
    changes = {}
    for field in FIELD_VALIDATORS:
        current = getattr(room, field)
        marker = object()
        new = ask(f"{field} [{current}]: ", FIELD_VALIDATORS[field], default=marker)
        if new is not marker:
            changes[field] = new
    if changes:
        manager.update_room(room.room_id, **changes)
        print(f"Updated: {room}")
    else:
        print("Nothing changed.")


def save_rooms(manager):
    manager.save_csv(ROOMS_CSV)
    print(f"Saved {len(manager.rooms)} room(s) to {os.path.relpath(ROOMS_CSV, BASE_DIR)}")


# ----------------------------------------------------------------------------
# Module 2 actions
# ----------------------------------------------------------------------------
def require_rooms(manager):
    if not manager.rooms:
        print("Add or load rooms first (Module 1).")
        return False
    return True


def load_readings(analysis):
    path = input(f"Readings CSV [{os.path.relpath(READINGS_CSV, BASE_DIR)}]: ").strip() or READINGS_CSV
    try:
        report = analysis.load(path)
    except (OSError, ValueError) as err:
        print(f"Could not load readings: {err}")
        return
    print("\nCleaning report")
    for key, value in report.items():
        print(f"  {key.replace('_', ' '):<30}{value}")
    filled = ca.filled_rows(analysis.clean)
    if not filled.empty:
        print("  Filled values (linear interpolation within each room):")
        for _, row in filled.iterrows():
            print(f"    {row['room_id']} {row['date']:%Y-%m-%d} -> {row['actual_kwh']:.2f} kWh")


def get_costed(manager, analysis, price):
    """Merge cleaned readings with the current rooms and add cost."""
    if analysis.clean is None:
        print("Load the readings first (option 7).")
        return None
    if not require_rooms(manager):
        return None
    costed, unmatched = analysis.costed(manager.to_dataframe(), price)
    if unmatched:
        print(f"Warning: no room data for {', '.join(unmatched)} - those readings are skipped.")
    return costed


def cost_report(manager, analysis):
    if analysis.clean is None:
        print("Load the readings first (option 7).")
        return
    price = ask_price(analysis.price)
    costed = get_costed(manager, analysis, price)
    if costed is None:
        return
    tables = ca.build_tables(costed)
    for name in ("consumption_by_room", "consumption_by_building", "consumption_by_month"):
        print(f"\n{name.replace('_', ' ').title()} (price {price:g}/kWh)")
        print(tables[name].to_string(index=False))


def ac_scenario(manager, analysis):
    if not require_rooms(manager):
        return
    pct = ask_percent()
    price = ask_price(analysis.price)
    analysis.price = price
    scenario = ca.ac_reduction_scenario(manager.to_dataframe(), pct, price)
    analysis.scenario, analysis.scenario_pct = scenario, pct
    print(f"\nEstimated daily energy with air-conditioning power reduced by {pct:g}%")
    print(scenario[["room_id", "room_name", "ac_kw_before", "ac_kw_after", "before_kwh_day",
                    "after_kwh_day", "saving_kwh_day", "saving_pct"]].to_string(index=False))
    before, after, saving, saving_pct = ca.scenario_totals(scenario)
    print(f"\nTotal before: {before:,.1f} kWh/day | after: {after:,.1f} kWh/day | "
          f"saving: {saving:,.1f} kWh/day ({saving_pct:.1f}%)")
    print(f"Over 30 days: {saving * 30:,.0f} kWh = {saving * 30 * price:,.2f} currency units")


def make_charts(manager, analysis):
    if analysis.clean is None:
        print("Load the readings first (option 7).")
        return
    price = ask_price(analysis.price)
    costed = get_costed(manager, analysis, price)
    if costed is None:
        return
    for path in ca.save_charts(costed, price, CHARTS_DIR):
        print(f"Saved {os.path.relpath(path, BASE_DIR)}")


def export_reports(manager, analysis):
    if analysis.clean is None:
        print("Load the readings first (option 7).")
        return
    price = ask_price(analysis.price)
    costed = get_costed(manager, analysis, price)
    if costed is None:
        return
    tables = ca.build_tables(costed)
    tables["cleaned_readings"] = analysis.clean.drop(columns="was_missing")
    tables["filled_values"] = ca.filled_rows(analysis.clean)
    if analysis.scenario is not None:
        tables["ac_reduction_scenario"] = analysis.scenario
    else:
        print("(AC scenario not run yet - choose option 9 first to include it.)")
    for path in ca.export_reports(tables, REPORTS_DIR):
        print(f"Saved {os.path.relpath(path, BASE_DIR)}")


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def main():
    manager = RoomManager()
    analysis = ca.ConsumptionAnalysis()

    if os.path.exists(ROOMS_CSV):
        count, errors = manager.load_csv(ROOMS_CSV)
        print(f"Loaded {count} room(s) from {os.path.relpath(ROOMS_CSV, BASE_DIR)}.")
        for err in errors:
            print(f"  Skipped - {err}")

    actions = {
        "1": lambda: add_room(manager),
        "2": lambda: list_rooms(manager),
        "3": lambda: search_rooms(manager),
        "4": lambda: update_room(manager),
        "5": lambda: print(manager.summary_text()),
        "6": lambda: save_rooms(manager),
        "7": lambda: load_readings(analysis),
        "8": lambda: cost_report(manager, analysis),
        "9": lambda: ac_scenario(manager, analysis),
        "10": lambda: make_charts(manager, analysis),
        "11": lambda: export_reports(manager, analysis),
    }

    while True:
        print(MENU)
        try:
            choice = input("Choose an option: ").strip()
        except EOFError:
            break
        if choice == "0":
            print("Goodbye!")
            break
        action = actions.get(choice)
        if action is None:
            print("Please choose a number from the menu.")
            continue
        try:
            action()
        except (RuntimeError, KeyError, ValueError, OSError) as err:
            print(f"Error: {err}")


if __name__ == "__main__":
    main()
