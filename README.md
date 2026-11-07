# Building Energy Analyzer

**Student name:** *Salma Khatab*

## Project description

A Python application that calculates and analyzes the energy consumption of rooms in two buildings
(Admin Block and Academic Block). It has two connected modules, joined by a menu in `main.py`:

1. **Energy Consumption Calculator** (`energy\_calculator.py`) - a `Room` class and a `RoomManager` class to
add, list, search and update rooms; calculates daily energy (kWh) = total power (kW) x operating hours,
the total, and consumption per m2; saves room data to CSV. Inputs are validated (area > 0, power >= 0,
hours between 0 and 24).
2. **Consumption and Cost Analysis** (`cost\_analysis.py`) - reads actual daily readings, cleans them with pandas
(duplicates, missing values), merges them with the room data, calculates consumption and cost per room,
building and month for a price per kWh entered by the user, uses NumPy to compare estimated consumption
before/after reducing air-conditioning power by a chosen percentage, draws four Matplotlib charts
(line, bar, scatter, histogram), and exports CSV reports and PNG charts.

## Required libraries

Python 3.9+ and: `pandas`, `numpy`, `matplotlib` (plus `notebook` to open the notebook).

```
pip install -r requirements.txt
```

## How to run

```
python main.py            # menu application
python run\_tests.py       # 3 valid + 3 invalid test cases -> reports/test\_results.csv
jupyter notebook notebooks/analysis.ipynb
```

Suggested order in the menu: **7** (load and clean readings) -> **8** (cost report, enter a price) ->
**9** (AC reduction, enter a percentage) -> **10** (charts) -> **11** (export reports).
Options 1-6 manage the rooms (Module 1); rooms are loaded from `data/rooms.csv` at start-up.

## Folder contents

|Path|Content|
|-|-|
|`main.py`|menu that connects the two modules|
|`energy\_calculator.py`|Module 1|
|`cost\_analysis.py`|Module 2|
|`run\_tests.py`|test cases (expected vs actual)|
|`data/rooms.csv`, `data/readings.csv`|sample data: 8 rooms, 2 buildings, 61 daily readings per room (Aug-Sep 2026)|
|`notebooks/analysis.ipynb`|short notebook explaining the analysis|
|`reports/`|CSV reports (price used in the sample run: 1.5 per kWh; AC reduction: 20%)|
|`charts/`|the four PNG charts|

## Data cleaning decisions

* Duplicate rows (same room and date) are removed, keeping the first one (2 found).
* A missing kWh value is filled by linear interpolation between the previous and next day of the same room (3 found);
the filled values are listed in `reports/filled\_values.csv`.

