"""Synthetic seed data so all 25 analytics queries have enough rows to work on.

IMPORTANT: everything created here is SAMPLE data, not real cricket records.
Seed rows use IDs >= 900_000 so they are easy to tell apart from API rows.
Venue capacities are approximate. Player names are fictional.
"""
import random
from collections import defaultdict
from datetime import date, timedelta

from utils import db_connection as db

SEED_ID = 900_000
N_MATCHES = 450
START_DATE = date(2020, 1, 1)

# team -> (country, first names, last names, strength)
TEAMS = {
    "India": ("India", ["Arjun", "Rohan", "Vikram", "Kabir", "Aditya", "Nikhil", "Sameer"],
              ["Sharma", "Verma", "Patel", "Nair", "Reddy", "Mehta", "Chopra"], 1.10),
    "Australia": ("Australia", ["Jack", "Liam", "Mitchell", "Cameron", "Tom", "Riley", "Harry"],
                  ["Walker", "Fraser", "Dawson", "Brooks", "Hughes", "Palmer", "Stanton"], 1.08),
    "England": ("England", ["Oliver", "George", "Harvey", "Archie", "Freddie", "Theo", "Callum"],
                ["Hartley", "Whitmore", "Ashford", "Calloway", "Fenwick", "Thornton", "Pemberton"], 1.03),
    "South Africa": ("South Africa", ["Thabo", "Pieter", "Johan", "Sipho", "Dewald", "Lwazi", "Ruan"],
                     ["Mokoena", "Botha", "Venter", "Dlamini", "Pretorius", "Naidoo", "Kruger"], 1.00),
    "New Zealand": ("New Zealand", ["Finn", "Hamish", "Ben", "Callan", "Rhys", "Tane", "Jacob"],
                    ["Tamihana", "Cooper", "Henare", "Larkin", "Ormond", "Pickett", "McRae"], 0.97),
    "Pakistan": ("Pakistan", ["Hamza", "Faizan", "Salman", "Usman", "Zeeshan", "Imran", "Kamran"],
                 ["Qureshi", "Siddiqui", "Rana", "Chaudhry", "Bukhari", "Abbasi", "Mirza"], 0.95),
    "Sri Lanka": ("Sri Lanka", ["Ravindu", "Sahan", "Lakshan", "Dinesh", "Pasindu", "Hasitha", "Oshada"],
                  ["Jayasekara", "Wickramage", "Gunaratne", "Peiris", "Samarasinghe",
                   "Rajapaksa", "Abeywickrama"], 0.92),
    "West Indies": ("West Indies", ["Kyle", "Darren", "Marlon", "Andre", "Jason", "Tyrone", "Rashid"],
                    ["Alleyne", "Burrowes", "Gittens", "Maynard", "Phillip", "Redman", "Springer"], 0.90),
}

# (name, city, country, approximate capacity)
VENUES = [
    ("Eden Gardens", "Kolkata", "India", 66000),
    ("Narendra Modi Stadium", "Ahmedabad", "India", 132000),
    ("Wankhede Stadium", "Mumbai", "India", 33000),
    ("Melbourne Cricket Ground", "Melbourne", "Australia", 100000),
    ("Sydney Cricket Ground", "Sydney", "Australia", 48000),
    ("Lord's", "London", "England", 31000),
    ("The Oval", "London", "England", 27500),
    ("Newlands", "Cape Town", "South Africa", 25000),
    ("Wanderers Stadium", "Johannesburg", "South Africa", 34000),
    ("Eden Park", "Auckland", "New Zealand", 50000),
    ("Gaddafi Stadium", "Lahore", "Pakistan", 34000),
    ("Galle International Stadium", "Galle", "Sri Lanka", 35000),
    ("Sabina Park", "Kingston", "West Indies", 20000),
    ("Kensington Oval", "Bridgetown", "West Indies", 28000),
]

# Squad order: XI first (batting order), then 4 reserves
SQUAD_ROLES = (["Batsman"] * 4 + ["Wicket-keeper"] + ["All-rounder"] * 3
               + ["Bowler"] * 3 + ["Bowler", "Bowler", "Batsman", "All-rounder"])
BOWL_STYLES = ["Right-arm fast", "Left-arm fast", "Right-arm offbreak",
               "Left-arm orthodox", "Legbreak", "Right-arm medium"]
FORMATS = ["Test", "ODI", "T20I"]
POS_MEANS = {  # average runs by batting position 1..11
    "T20I": [28, 26, 24, 20, 17, 14, 10, 7, 5, 3, 2],
    "ODI": [48, 45, 42, 36, 30, 24, 18, 12, 8, 5, 3],
    "Test": [42, 40, 38, 34, 30, 26, 20, 14, 10, 6, 4],
}
STRIKE = {"T20I": (115, 155), "ODI": (70, 100), "Test": (42, 62)}
ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(n):
    return ORDINALS.get(n if n < 4 else 0, f"{n}th") if not 10 < n % 100 < 14 else f"{n}th"


def _upsert_reference(rng):
    """Insert teams and venues (reusing API rows when the name already exists)."""
    team_ids = {}
    for i, (name, (country, *_rest)) in enumerate(TEAMS.items(), start=1):
        existing = db.run_query(
            "SELECT team_id FROM teams WHERE team_name = :n", {"n": name})
        if len(existing):
            team_id = int(existing["team_id"].iloc[0])
            db.execute("UPDATE teams SET country = :c WHERE team_id = :i",
                       {"c": country, "i": team_id})
        else:
            team_id = SEED_ID + i
            db.upsert_rows("teams", [{"team_id": team_id, "team_name": name,
                                      "short_name": name[:3].upper(),
                                      "country": country}], ["team_id"])
        team_ids[name] = team_id

    venue_rows = []
    for i, (name, city, country, cap) in enumerate(VENUES, start=1):
        existing = db.run_query(
            "SELECT venue_id FROM venues WHERE venue_name = :n", {"n": name})
        if len(existing):
            vid = int(existing["venue_id"].iloc[0])
            db.execute("UPDATE venues SET city = :ci, country = :co, capacity = :ca "
                       "WHERE venue_id = :i",
                       {"ci": city, "co": country, "ca": cap, "i": vid})
        else:
            vid = SEED_ID + i
            db.upsert_rows("venues", [{"venue_id": vid, "venue_name": name,
                                       "city": city, "country": country,
                                       "capacity": cap}], ["venue_id"])
        venue_rows.append({"id": vid, "country": country})
    return team_ids, venue_rows


def _make_players(rng, team_ids):
    """15 fictional players per team; first 11 form the playing XI."""
    players, squads = [], {}
    pid = SEED_ID
    for team, (country, firsts, lasts, _s) in TEAMS.items():
        combos = [(first, last) for first in firsts for last in lasts]
        rng.shuffle(combos)
        squad = []
        for (first, last), role in zip(combos, SQUAD_ROLES):
            pid += 1
            bowl = (rng.choice(BOWL_STYLES)
                    if role in ("Bowler", "All-rounder") else None)
            row = {"player_id": pid, "full_name": f"{first} {last}",
                   "country": country, "playing_role": role,
                   "batting_style": rng.choice(["Right-hand bat", "Left-hand bat"]),
                   "bowling_style": bowl}
            players.append(row)
            squad.append(row)
        squads[team] = squad
    db.upsert_rows("players", players, ["player_id"])
    return squads


def _career_stats(rng, squads):
    """Career totals per player and format (independent of the sample matches)."""
    base_avg = {"Batsman": (34, 54), "Wicket-keeper": (28, 42),
                "All-rounder": (26, 40), "Bowler": (8, 18)}
    rows = []
    for squad in squads.values():
        for p in squad:
            fmts = [f for f, prob in zip(FORMATS, (0.6, 0.85, 0.8))
                    if rng.random() < prob] or ["ODI"]
            for fmt in fmts:
                lo, hi = {"Test": (15, 120), "ODI": (30, 250), "T20I": (20, 120)}[fmt]
                matches = rng.randint(lo, hi)
                innings = int(matches * (1.8 if fmt == "Test" else 0.92))
                not_outs = int(innings * 0.1)
                avg = rng.uniform(*base_avg[p["playing_role"]])
                if fmt == "T20I":
                    avg *= 0.75
                runs = int(avg * max(1, innings - not_outs))
                real_avg = round(runs / max(1, innings - not_outs), 2)
                batter = p["playing_role"] != "Bowler"
                w_rate = {"Test": (2.0, 3.2), "ODI": (1.2, 2.0), "T20I": (0.9, 1.6)}[fmt]
                if p["playing_role"] == "Bowler":
                    wickets = int(matches * rng.uniform(*w_rate))
                elif p["playing_role"] == "All-rounder":
                    wickets = int(matches * rng.uniform(*w_rate) * 0.45)
                else:
                    wickets = 0
                bavg = {"Test": (24, 34), "ODI": (26, 38), "T20I": (20, 30)}[fmt]
                econ = {"Test": (2.6, 3.4), "ODI": (4.2, 5.6), "T20I": (7.0, 8.8)}[fmt]
                rows.append({
                    "player_id": p["player_id"], "format": fmt, "matches": matches,
                    "innings": innings, "runs": runs,
                    "highest_score": min(runs, int(avg * rng.uniform(2.5, 4.5))),
                    "batting_avg": real_avg,
                    "strike_rate": round(rng.uniform(*STRIKE[fmt]), 2),
                    "centuries": int(runs * rng.uniform(0.002, 0.004) * (1 if batter else 0.1)),
                    "fifties": int(runs * rng.uniform(0.006, 0.010)),
                    "wickets": wickets,
                    "bowling_avg": round(rng.uniform(*bavg), 2) if wickets else None,
                    "economy_rate": round(rng.uniform(*econ), 2) if wickets else None,
                    "catches": int(matches * rng.uniform(0.2, 0.9)),
                    "stumpings": (int(matches * rng.uniform(0.1, 0.5))
                                  if p["playing_role"] == "Wicket-keeper" else 0)})
    db.upsert_rows("player_career_stats", rows, ["player_id", "format"])
    return len(rows)


def _batting_innings(rng, xi, fmt, strength, match_id, innings_no, team_id):
    rows = []
    for pos, p in enumerate(xi, start=1):
        if fmt != "Test" and pos >= 9 and rng.random() < 0.4:
            continue  # did not bat
        mean = POS_MEANS[fmt][pos - 1] * strength
        runs = min(int(rng.expovariate(1 / max(mean, 1))), 220)
        sr = rng.uniform(*STRIKE[fmt])
        balls = max(1, int(runs / sr * 100)) if runs else rng.randint(1, 6)
        fours = int(runs * rng.uniform(0.04, 0.10))
        sixes = int(runs * rng.uniform(0.0, 0.06 if fmt != "Test" else 0.02))
        rows.append({"match_id": match_id, "player_id": p["player_id"],
                     "team_id": team_id, "innings_no": innings_no,
                     "batting_position": pos, "runs": runs, "balls_faced": balls,
                     "fours": fours, "sixes": sixes,
                     "strike_rate": round(runs / balls * 100, 2),
                     "is_out": 1 if rng.random() < 0.82 else 0})
    outs = sum(r["is_out"] for r in rows)
    if outs > 10:  # a side can lose at most 10 wickets
        for r in reversed(rows):
            if r["is_out"]:
                r["is_out"] = 0
                break
    return rows


def _bowling_innings(rng, bowlers, fmt, match_id, innings_no, team_id, total_runs, wickets):
    """Split an innings' runs and wickets among the fielding side's bowlers."""
    chosen = rng.sample(bowlers, min(5, len(bowlers)))
    if fmt == "T20I":
        overs = [4] * len(chosen)
    elif fmt == "ODI":
        overs = [10] * len(chosen)
    else:
        total = rng.randint(80, 130)
        weights = [rng.uniform(0.6, 1.4) for _ in chosen]
        overs = [max(8, min(30, round(total * w / sum(weights)))) for w in weights]
    total_overs = sum(overs)
    runs_split = [int(total_runs * o / total_overs) for o in overs]
    runs_split[0] += total_runs - sum(runs_split)
    wk = [0] * len(chosen)
    for _ in range(wickets):
        wk[rng.randrange(len(chosen))] += 1
    return [{"match_id": match_id, "player_id": p["player_id"], "team_id": team_id,
             "innings_no": innings_no, "overs": float(o),
             "maidens": rng.randint(0, 2) if fmt != "T20I" else 0,
             "runs_conceded": r, "wickets": w, "economy_rate": round(r / o, 2)}
            for p, o, r, w in zip(chosen, overs, runs_split, wk)]


def _generate_matches(rng, team_ids, venue_rows, squads):
    names = list(TEAMS)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    today = date.today()
    span = (today - START_DATE).days
    dates = sorted([START_DATE + timedelta(days=rng.randint(0, span))
                    for _ in range(N_MATCHES - 12)]
                   + [today - timedelta(days=rng.randint(0, 28)) for _ in range(12)])

    venues_by_country = defaultdict(list)
    for v in venue_rows:
        venues_by_country[v["country"]].append(v)

    matches, bat_rows, bowl_rows = [], [], []
    series_info = {}              # (year, fmt) -> dict
    series_counter = defaultdict(int)

    for i, match_date in enumerate(dates):
        a, b = pairs[i % len(pairs)]
        if rng.random() < 0.5:
            a, b = b, a
        fmt = rng.choices(FORMATS, weights=[0.2, 0.4, 0.4])[0]
        home_country = TEAMS[a][0]
        venue = (rng.choice(venues_by_country[home_country])
                 if rng.random() < 0.6 and venues_by_country[home_country]
                 else rng.choice(venue_rows))
        match_id = SEED_ID + 1 + i
        key = (match_date.year, fmt)
        if key not in series_info:
            series_info[key] = {"series_id": SEED_ID + 1 + len(series_info),
                                "start": match_date, "host": venue["country"]}
        sid = series_info[key]["series_id"]
        series_counter[key] += 1
        desc = f"{_ordinal(series_counter[key])} {fmt}"

        toss_winner = rng.choice([a, b])
        decision = ("bat" if rng.random() < (0.7 if fmt == "Test" else 0.45) else "bowl")
        first = toss_winner if decision == "bat" else (b if toss_winner == a else a)
        second = b if first == a else a

        row = {"match_id": match_id, "series_id": sid, "match_desc": desc,
               "match_format": fmt, "match_date": match_date.isoformat(),
               "team1_id": team_ids[a], "team2_id": team_ids[b],
               "venue_id": venue["id"], "toss_winner_id": team_ids[toss_winner],
               "toss_decision": decision, "winner_id": None,
               "victory_margin": None, "victory_type": None, "state": "Complete"}

        if rng.random() < 0.03:   # abandoned: no result, no scorecard
            row.update(victory_type="no result", state="Abandoned")
            matches.append(row)
            continue

        plan = ([(1, first), (2, second), (3, first), (4, second)]
                if fmt == "Test" else [(1, first), (2, second)])
        innings = {}
        for inn_no, team in plan:
            xi = squads[team][:11]
            innings[inn_no] = (team, _batting_innings(
                rng, xi, fmt, TEAMS[team][3], match_id, inn_no, team_ids[team]))

        total = defaultdict(int)
        for inn_no, (team, rows) in innings.items():
            total[team] += sum(r["runs"] for r in rows)
        last_inn = max(innings)

        if total[first] == total[second]:
            row.update(victory_type="tie")
        elif total[second] > total[first]:
            # chasing side won: it cannot have lost all 10 wickets
            rows = innings[last_inn][1]
            if sum(r["is_out"] for r in rows) >= 10:
                for r in reversed(rows):
                    if r["is_out"]:
                        r["is_out"] = 0
                        break
            outs = sum(r["is_out"] for r in rows)
            row.update(winner_id=team_ids[second], victory_type="wickets",
                       victory_margin=max(1, 10 - outs))
        else:
            row.update(winner_id=team_ids[first], victory_type="runs",
                       victory_margin=total[first] - total[second])

        for inn_no, (team, rows) in innings.items():
            bat_rows.extend(rows)
            fielding = second if team == first else first
            bowlers = [p for p in squads[fielding][:11]
                       if p["playing_role"] in ("Bowler", "All-rounder")]
            extras = rng.randint(5, 25) if fmt == "Test" else rng.randint(2, 14)
            bowl_rows.extend(_bowling_innings(
                rng, bowlers, fmt, match_id, inn_no, team_ids[fielding],
                sum(r["runs"] for r in rows) + extras,
                sum(r["is_out"] for r in rows)))
        matches.append(row)

    series_rows = []
    for (year, fmt), info in series_info.items():
        series_rows.append({
            "series_id": info["series_id"],
            "series_name": f"Sample {fmt} Series {year}",
            "host_country": info["host"], "match_type": fmt,
            "start_date": info["start"].isoformat(),
            "total_matches": series_counter[(year, fmt)]})
    return series_rows, matches, bat_rows, bowl_rows


def wipe_seed():
    """Delete every seed row (IDs >= SEED_ID), children before parents."""
    for sql in [
        "DELETE FROM batting_performances WHERE match_id >= :b",
        "DELETE FROM bowling_performances WHERE match_id >= :b",
        "DELETE FROM matches WHERE match_id >= :b",
        "DELETE FROM series WHERE series_id >= :b",
        "DELETE FROM player_career_stats WHERE player_id >= :b",
        "DELETE FROM players WHERE player_id >= :b",
        "DELETE FROM venues WHERE venue_id >= :b",
        "DELETE FROM teams WHERE team_id >= :b",
    ]:
        db.execute(sql, {"b": SEED_ID})


def run_seed(seed=42):
    """Build the whole seed dataset (safe to re-run: rows are upserted)."""
    rng = random.Random(seed)
    team_ids, venue_rows = _upsert_reference(rng)
    squads = _make_players(rng, team_ids)
    n_career = _career_stats(rng, squads)
    series_rows, matches, bat_rows, bowl_rows = _generate_matches(
        rng, team_ids, venue_rows, squads)
    db.upsert_rows("series", series_rows, ["series_id"])
    db.upsert_rows("matches", matches, ["match_id"])
    db.upsert_rows("batting_performances", bat_rows,
                   ["match_id", "player_id", "innings_no"])
    db.upsert_rows("bowling_performances", bowl_rows,
                   ["match_id", "player_id", "innings_no"])
    return {"players": sum(len(s) for s in squads.values()),
            "career_rows": n_career, "series": len(series_rows),
            "matches": len(matches), "batting_rows": len(bat_rows),
            "bowling_rows": len(bowl_rows)}
