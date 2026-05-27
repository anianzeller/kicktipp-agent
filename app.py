import os
import time
import requests
from flask import Flask, render_template, redirect, url_for
from datetime import datetime, timezone
from kicktipp_optimizer import analyze_match

app = Flask(__name__)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
SPORT_KEY = os.environ.get("SPORT_KEY", "soccer_fifa_world_cup")
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "7200"))

_cache = {"data": None, "ts": 0.0, "error": None}


def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds/"
    resp = requests.get(
        url,
        params={
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def build_tips(raw_matches):
    now_utc = datetime.now(timezone.utc)
    tips = []

    for match in raw_matches:
        commence_str = match["commence_time"].replace("Z", "+00:00")
        commence = datetime.fromisoformat(commence_str)

        if commence < now_utc:
            continue

        home = match["home_team"]
        away = match["away_team"]

        home_odds_list, draw_odds_list, away_odds_list = [], [], []
        for bm in match.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                if home in outcomes and away in outcomes and "Draw" in outcomes:
                    home_odds_list.append(outcomes[home])
                    draw_odds_list.append(outcomes["Draw"])
                    away_odds_list.append(outcomes[away])

        if not home_odds_list:
            continue

        o1 = sum(home_odds_list) / len(home_odds_list)
        ox = sum(draw_odds_list) / len(draw_odds_list)
        o2 = sum(away_odds_list) / len(away_odds_list)

        try:
            result = analyze_match(home, away, (o1, ox, o2), verbose=False)
        except Exception:
            continue

        tips.append({
            "home": home,
            "away": away,
            "date": commence.strftime("%d.%m."),
            "time": commence.strftime("%H:%M"),
            "odds_1": round(o1, 2),
            "odds_x": round(ox, 2),
            "odds_2": round(o2, 2),
            "tip": result["recommended_tip"],
            "ev": result["recommended_ev"],
            "ev_pct": min(int(result["recommended_ev"] / 4 * 100), 100),
            "top_tips": result["top_tips"][:4],
            "close_call": result["close_call"],
            "implied_1": f"{result['implied_probs']['1']:.0%}",
            "implied_x": f"{result['implied_probs']['X']:.0%}",
            "implied_2": f"{result['implied_probs']['2']:.0%}",
            "n_bookmakers": len(home_odds_list),
        })

    tips.sort(key=lambda x: (x["date"], x["time"]))
    return tips


def get_tips():
    if _cache["data"] is not None and time.time() - _cache["ts"] < CACHE_TTL:
        return _cache["data"], _cache["error"]

    if not ODDS_API_KEY:
        err = "ODDS_API_KEY ist nicht gesetzt. Bitte als Umgebungsvariable konfigurieren."
        return [], err

    try:
        raw = fetch_odds()
        tips = build_tips(raw)
        _cache["data"] = tips
        _cache["ts"] = time.time()
        _cache["error"] = None
        return tips, None
    except requests.HTTPError as e:
        msg = f"API-Fehler {e.response.status_code}: {e.response.text[:200]}"
        _cache["error"] = msg
        return _cache["data"] or [], msg
    except Exception as e:
        _cache["error"] = str(e)
        return _cache["data"] or [], str(e)


def format_updated(ts):
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


@app.route("/")
def index():
    tips, error = get_tips()
    return render_template(
        "index.html",
        tips=tips,
        error=error,
        updated=format_updated(_cache["ts"]),
        cache_ttl_min=CACHE_TTL // 60,
    )


@app.route("/refresh")
def refresh():
    _cache["ts"] = 0.0
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
