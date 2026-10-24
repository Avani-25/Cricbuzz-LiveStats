import json

import pytest

import config
from api.cricbuzz_client import CricbuzzAPIError
from services import live_service as live
from utils import db_connection as db

LIVE_JSON = {"typeMatches": [{"matchType": "International", "seriesMatches": [
    {"seriesAdWrapper": {"seriesId": 7, "seriesName": "Tri-Nation Series", "matches": [
        {"matchInfo": {"matchId": 101, "seriesId": 7, "matchDesc": "1st Match",
                       "matchFormat": "ODI", "state": "In Progress", "status": "Zimbabwe opt to bat",
                       "startDate": "1792300635000",
                       "team1": {"teamId": 12, "teamName": "Zimbabwe", "teamSName": "ZIM"},
                       "team2": {"teamId": 6, "teamName": "Bangladesh", "teamSName": "BAN"},
                       "venueInfo": {"id": 55, "ground": "Sheikh Zayed Stadium", "city": "Abu Dhabi"}},
         "matchScore": {"team1Score": {"inngs1": {"runs": 245, "wickets": 6, "overs": 50}},
                        "team2Score": {"inngs1": {"runs": 90, "wickets": 10, "overs": 21.3}}}},
        {"matchInfo": {"matchId": 102, "seriesId": 7, "matchDesc": "2nd Match",
                       "matchFormat": "ODI", "state": "Complete", "status": "Canada won by 24 runs",
                       "team1": {"teamId": 26, "teamName": "Canada", "teamSName": "CAN"},
                       "team2": {"teamId": 72, "teamName": "Nepal", "teamSName": "NEP"},
                       "venueInfo": {"id": 56, "ground": "Al Amerat", "city": "Muscat"}}},
        {"matchInfo": {"matchId": None}}]}},
    {"adDetail": {"name": "ad"}}]}]}

SCORECARD = {"scoreCard": [{"inningsId": 1,
    "batTeamDetails": {"batTeamName": "Canada", "batsmenData": {
        "bat_1": {"batName": "A Batter", "runs": 55, "balls": 60, "fours": 5, "sixes": 1,
                  "strikeRate": 91.6, "outDesc": "c X b Y"}}},
    "bowlTeamDetails": {"bowlersData": {
        "bowl_1": {"bowlName": "B Bowler", "overs": 10, "maidens": 1, "runs": 40,
                   "wickets": 3, "economy": 4.0}}},
    "scoreDetails": {"runs": 250, "wickets": 8, "overs": 50}}]}


class FakeClient:
    fail = False
    saved = None
    quota_remaining = "123"

    def get(self, path, params=None, use_cache=True, retries=None):
        if FakeClient.fail:
            raise CricbuzzAPIError("503 for test")
        return SCORECARD if "scard" in path else LIVE_JSON

    def _cache_file(self, path, params):
        return FakeClient.saved


@pytest.fixture(autouse=True)
def fake(monkeypatch, tmp_path):
    FakeClient.fail = False
    FakeClient.saved = tmp_path / "saved.json"
    monkeypatch.setattr(live, "CricbuzzClient", FakeClient)
    config.DATABASE_URL = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    db._engine = None
    db.init_db()
    yield
    db.get_engine().dispose()
    db._engine = None


def test_matches_to_frame_parses_scores_and_skips_bad_rows():
    df = live.matches_to_frame(LIVE_JSON)
    assert list(df["match_id"]) == [101, 102]
    row = df.iloc[0]
    assert row["score1"] == "245/6 (50)"
    assert row["score2"] == "90 (21.3)"          # all out: no '/10'
    assert row["venue"] == "Sheikh Zayed Stadium" and row["start_utc"].endswith("UTC")
    assert df.iloc[1]["score1"] == ""


def test_empty_or_odd_json_does_not_crash():
    assert live.matches_to_frame({}).empty
    assert live.matches_to_frame(None).empty
    assert live.matches_to_frame({"typeMatches": [{"seriesMatches": [{"seriesAdWrapper": None}]}]}).empty


def test_state_icons():
    assert live.state_icon("In Progress") == "🟢"
    assert live.state_icon("Complete") == "⚪"
    assert live.state_icon("Delay") == "🟠"
    assert live.state_icon("Toss") == "🔵"
    assert live.state_icon("") == "⚫"


def test_fetch_ok():
    data, meta = live.fetch_matches("Live")
    assert data == LIVE_JSON and not meta["stale"] and meta["quota"] == "123"


def test_fetch_falls_back_to_saved_response():
    FakeClient.saved.write_text(json.dumps(LIVE_JSON))
    FakeClient.fail = True
    data, meta = live.fetch_matches("Live")
    assert data == LIVE_JSON and meta["stale"] and "503" in meta["error"]
    assert "server problem" in meta["friendly"]


def test_fetch_fails_cleanly_without_saved_response():
    FakeClient.fail = True
    data, meta = live.fetch_matches("Recent")
    assert data is None and "503" in meta["error"] and "server problem" in meta["friendly"]


def test_missing_endpoint_is_reported(monkeypatch):
    monkeypatch.setitem(config.ENDPOINTS, "recent_matches", "TODO")
    data, meta = live.fetch_matches("Recent")
    assert data is None and "recent_matches" in meta["error"]


def test_sync_to_db_saves_and_is_repeatable():
    ok, message = live.sync_to_db(LIVE_JSON)
    assert ok, message
    live.sync_to_db(LIVE_JSON)                    # second run updates, never duplicates
    counts = db.table_counts()
    assert counts["matches"] == 2 and counts["teams"] == 4 and counts["venues"] == 2
    row = db.run_query("SELECT winner_id, victory_type, victory_margin "
                       "FROM matches WHERE match_id=102").iloc[0]
    assert (row.winner_id, row.victory_type, row.victory_margin) == (26, "runs", 24)


def test_scorecard_tables():
    tables = live.scorecard_tables(SCORECARD)
    assert len(tables) == 1
    title, bat, bowl = tables[0]
    assert "Canada" in title and "250/8" in title
    assert list(bat.columns)[:3] == ["Batter", "R", "B"] and bowl.iloc[0]["W"] == 3
    assert live.scorecard_tables({"unexpected": 1}) == []
    assert live.scorecard_tables(None) == []


def test_scorecard_endpoint_missing(monkeypatch):
    monkeypatch.setitem(config.ENDPOINTS, "scorecard", "TODO")
    with pytest.raises(ValueError):
        live.fetch_scorecard(1)


def test_client_retries_without_a_pointless_final_sleep(monkeypatch):
    import requests

    from api import cricbuzz_client as cc

    sleeps = []
    monkeypatch.setattr(cc.time, "sleep", lambda s: sleeps.append(s))
    client = cc.CricbuzzClient()

    def offline(*args, **kwargs):
        raise requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(client.session, "get", offline)
    with pytest.raises(cc.CricbuzzAPIError):
        client.get("/x", use_cache=False, retries=2)
    assert sleeps == [3]                      # 2 attempts -> one wait, none after the last
    sleeps.clear()
    with pytest.raises(cc.CricbuzzAPIError):
        client.get("/x", use_cache=False)     # default retries (3)
    assert sleeps == [3, 6]
