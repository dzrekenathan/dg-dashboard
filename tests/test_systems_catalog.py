from datetime import date

from app.systems_catalog import build_system_directorate_map, load_phase_deadlines_seed


def test_build_system_directorate_map_uses_cluster_default():
    catalog = {
        "clusters": [
            {"code": "C2", "directorate_code": "GSL", "systems": [{"code": "S014"}, {"code": "S015"}]},
        ]
    }
    result = build_system_directorate_map(catalog)
    assert result == {"S014": "GSL", "S015": "GSL"}


def test_build_system_directorate_map_honors_per_system_override():
    catalog = {
        "clusters": [
            {"code": "C2", "directorate_code": "GSL", "systems": [{"code": "S014", "directorate": "CDT"}]},
        ]
    }
    result = build_system_directorate_map(catalog)
    assert result == {"S014": "CDT"}


def test_build_system_directorate_map_missing_directorate_code_defaults_to_general():
    catalog = {"clusters": [{"code": "C99", "systems": [{"code": "S999"}]}]}
    result = build_system_directorate_map(catalog)
    assert result == {"S999": "General"}


def test_load_phase_deadlines_seed_parses_real_catalog_file():
    seed = load_phase_deadlines_seed()
    assert set(seed.keys()) == {1, 2, 3, 4}
    assert all(isinstance(v, date) for v in seed.values())
