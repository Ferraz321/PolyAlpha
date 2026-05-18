from pathlib import Path


def next_commands(profile_dir: Path, db: Path, diagnostics: dict, candidates: list[dict]) -> list[dict]:
    commands = []
    sources = diagnostics.get("sources", {})
    if not sources.get("clob_features", {}).get("ready", False):
        commands.append(
            {
                "reason": "collect live CLOB snapshots for traded assets",
                "command": [
                    "cargo",
                    "run",
                    "--",
                    "watch-clob",
                    "--db",
                    str(db),
                    "--assets-file",
                    str(profile_dir / "clob_assets.txt"),
                ],
            }
        )
    if _needs_observations(candidates, diagnostics):
        commands.append(
            {
                "reason": "fetch external weather observations for actual-temperature factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-weather-open-meteo",
                    "--profile-dir",
                    str(profile_dir),
                    "--locations-csv",
                    "config/weather_locations.csv",
                    "--out",
                    str(profile_dir / "weather_observations.csv"),
                ],
                "status": "planned",
            }
        )
    if _needs_forecasts(candidates, diagnostics):
        commands.append(
            {
                "reason": "fetch external weather forecast history for forecast-error factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-weather-forecast-history",
                    "--profile-dir",
                    str(profile_dir),
                    "--locations-csv",
                    "config/weather_locations.csv",
                    "--out",
                    str(profile_dir / "forecast_history.csv"),
                ],
                "status": "implemented",
            }
        )
    commands.append(
        {
            "reason": "rerun full agent loop after adding data",
            "command": [
                "python",
                "profiler/profile_wallets.py",
                "agent",
                "--profile-dir",
                str(profile_dir),
                "--db",
                str(db),
                "--run-tools",
            ],
        }
    )
    return commands


def _needs_observations(candidates: list[dict], diagnostics: dict) -> bool:
    needed = any(item.get("required_data") == "external_weather_observation" for item in candidates)
    ready = diagnostics.get("sources", {}).get("weather_observations", {}).get("ready", False)
    return needed and not ready


def _needs_forecasts(candidates: list[dict], diagnostics: dict) -> bool:
    needed = any(item.get("required_data") == "external_weather_forecast" for item in candidates)
    ready = diagnostics.get("sources", {}).get("weather_forecasts", {}).get("ready", False)
    return needed and not ready
