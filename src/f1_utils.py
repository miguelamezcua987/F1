from pathlib import Path
import pandas as pd
import fastf1
import fastf1.plotting

CACHE_DIR = Path(__file__).parent.parent / "data" / "raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

CURRENT_YEAR = 2025

TEAM_COLORS: dict[str, str] = {
    "Red Bull Racing": "#3671C6",
    "Ferrari": "#E8002D",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",
    "RB": "#6692FF",
    "Kick Sauber": "#52E252",
    "Haas F1 Team": "#B6BABD",
}


def get_event_schedule(year: int) -> pd.DataFrame:
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    return schedule[["RoundNumber", "EventName", "Country", "EventDate", "EventFormat"]].copy()


def load_session(year: int, gp: str | int, session_type: str) -> fastf1.core.Session:
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=True, weather=False, messages=False)
    return session


def get_driver_laps(session: fastf1.core.Session, driver: str) -> pd.DataFrame:
    laps = session.laps.pick_drivers(driver).pick_quicklaps().reset_index(drop=True)
    return laps


def compare_drivers_fastest(
    session: fastf1.core.Session, drivers: list[str]
) -> pd.DataFrame:
    rows = []
    for drv in drivers:
        laps = session.laps.pick_drivers(drv)
        if laps.empty:
            continue
        fastest = laps.pick_fastest()
        rows.append(
            {
                "Driver": drv,
                "Team": fastest["Team"],
                "LapTime": fastest["LapTime"],
                "LapTimeSeconds": fastest["LapTime"].total_seconds() if pd.notna(fastest["LapTime"]) else None,
                "Sector1": fastest["Sector1Time"],
                "Sector2": fastest["Sector2Time"],
                "Sector3": fastest["Sector3Time"],
                "SpeedI1": fastest["SpeedI1"],
                "SpeedI2": fastest["SpeedI2"],
                "SpeedFL": fastest["SpeedFL"],
                "SpeedST": fastest["SpeedST"],
                "Compound": fastest["Compound"],
            }
        )
    df = pd.DataFrame(rows).sort_values("LapTimeSeconds").reset_index(drop=True)
    if not df.empty:
        df["Gap"] = df["LapTimeSeconds"] - df["LapTimeSeconds"].iloc[0]
    return df


def tyre_strategy(session: fastf1.core.Session, drivers: list[str]) -> pd.DataFrame:
    rows = []
    for drv in drivers:
        laps = session.laps.pick_drivers(drv)
        if laps.empty:
            continue
        stint_groups = laps.groupby("Stint")
        for stint_num, stint_laps in stint_groups:
            rows.append(
                {
                    "Driver": drv,
                    "Stint": stint_num,
                    "Compound": stint_laps["Compound"].iloc[0],
                    "StartLap": int(stint_laps["LapNumber"].min()),
                    "EndLap": int(stint_laps["LapNumber"].max()),
                    "Laps": len(stint_laps),
                }
            )
    return pd.DataFrame(rows)


def get_telemetry(session: fastf1.core.Session, driver: str) -> pd.DataFrame:
    fastest = session.laps.pick_drivers(driver).pick_fastest()
    tel = fastest.get_car_data().add_distance()
    tel["Driver"] = driver
    return tel
