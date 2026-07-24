import json
from datetime import date
from pathlib import Path

SYSTEMS_JSON_PATH = Path(__file__).resolve().parent.parent / "systems.json"


def _load_catalog() -> dict:
    with open(SYSTEMS_JSON_PATH) as f:
        return json.load(f)


def build_system_directorate_map(catalog: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for cluster in catalog.get("clusters", []):
        cluster_directorate = cluster.get("directorate_code", "General")
        for sys in cluster.get("systems", []):
            result[sys["code"]] = sys.get("directorate") or cluster_directorate
    return result


def load_phase_deadlines_seed() -> dict[int, date]:
    catalog = _load_catalog()
    return {
        row["phase"]: date.fromisoformat(row["deadline"])
        for row in catalog.get("phase_deadlines", [])
    }


def list_all_systems() -> list[dict]:
    catalog = _load_catalog()
    result: list[dict] = []
    for cluster in catalog.get("clusters", []):
        cluster_directorate = cluster.get("directorate_code", "General")
        for sys in cluster.get("systems", []):
            result.append({
                "code": sys["code"],
                "name": sys["name"],
                "phase": sys.get("phase"),
                "directorate": sys.get("directorate") or cluster_directorate,
                "description": sys.get("description", ""),
            })
    return result


SYSTEM_DIRECTORATE_MAP = build_system_directorate_map(_load_catalog())


def get_system_directorate(code: str) -> str | None:
    return SYSTEM_DIRECTORATE_MAP.get(code)
