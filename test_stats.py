import pytest

import config
from services import stats_service as stats
from utils import db_connection as db
from utils import seed_data


@pytest.fixture(scope="module", autouse=True)
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "t.db"
    config.DATABASE_URL = f"sqlite:///{path.as_posix()}"
    db._engine = None
    db.init_db()
    seed_data.run_seed()
    yield
    db.get_engine().dispose()
    db._engine = None


@pytest.mark.parametrize("fmt", ["Test", "ODI", "T20I"])
@pytest.mark.parametrize("metric", list(stats.BAT_METRICS))
def test_top_batters_sorted(fmt, metric):
    col, direction = stats.BAT_METRICS[metric]
    df = stats.top_batters(fmt, metric, 10, 10)
    assert 0 < len(df) <= 10
    ordered = df[col].is_monotonic_decreasing if direction == "DESC" else df[col].is_monotonic_increasing
    assert ordered


@pytest.mark.parametrize("metric", list(stats.BOWL_METRICS))
def test_top_bowlers_sorted(metric):
    col, direction = stats.BOWL_METRICS[metric]
    df = stats.top_bowlers("ODI", metric, 10, 20)
    assert len(df) > 0 and (df["wickets"] >= 20).all()
    assert df[col].is_monotonic_decreasing == (direction == "DESC") or len(df) == 1


def test_invalid_metric_never_reaches_sql():
    with pytest.raises(KeyError):
        stats.top_batters("ODI", "runs; DROP TABLE players", 5, 1)


def test_allrounders_and_leaders():
    assert len(stats.allrounders("ODI")) > 0
    bat, bowl = stats.leaders("Test")
    assert bat and bowl


def test_records_from_json_finds_nested_table():
    blob = {"meta": {"x": 1}, "rank": [{"name": "A", "pts": 1}, {"name": "B", "pts": 2},
                                       {"name": "C", "pts": 3}]}
    df = stats.records_from_json(blob)
    assert list(df["name"]) == ["A", "B", "C"]
    assert stats.records_from_json({"a": [1, 2]}) is None


def test_ranking_path_uses_registered_endpoint(monkeypatch):
    monkeypatch.setitem(config.ENDPOINTS, "top_stats", "/stats/v1/rankings/batsmen")
    assert stats.ranking_path("Bowlers") == "/stats/v1/rankings/bowlers"
    monkeypatch.setitem(config.ENDPOINTS, "top_stats", "TODO")
    assert stats.ranking_path("Bowlers") is None
