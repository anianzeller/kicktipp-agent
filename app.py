import os
import time
import requests
from flask import Flask, render_template, redirect, url_for
from datetime import datetime, timezone, timedelta
from kicktipp_optimizer import analyze_match

app = Flask(__name__)

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
SPORT_KEY = os.environ.get("SPORT_KEY", "soccer_fifa_world_cup")
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "7200"))

_cache = {"data": None, "ts": 0.0, "error": None}

# ── Flaggen-Emojis ────────────────────────────────────────────────────────────
FLAGS = {
    # Europa
    "Germany": "🇩🇪", "France": "🇫🇷", "Spain": "🇪🇸", "Portugal": "🇵🇹",
    "Netherlands": "🇳🇱", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Belgium": "🇧🇪", "Croatia": "🇭🇷",
    "Switzerland": "🇨🇭", "Austria": "🇦🇹", "Serbia": "🇷🇸", "Poland": "🇵🇱",
    "Denmark": "🇩🇰", "Ukraine": "🇺🇦", "Turkey": "🇹🇷", "Czech Republic": "🇨🇿",
    "Hungary": "🇭🇺", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Slovakia": "🇸🇰", "Romania": "🇷🇴",
    "Greece": "🇬🇷", "Albania": "🇦🇱", "Slovenia": "🇸🇮", "Iceland": "🇮🇸",
    "Norway": "🇳🇴", "Sweden": "🇸🇪", "Finland": "🇫🇮", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "North Macedonia": "🇲🇰", "Bosnia and Herzegovina": "🇧🇦",
    "Bosnia & Herzegovina": "🇧🇦", "Kosovo": "🇽🇰",
    # Americas
    "Brazil": "🇧🇷", "Argentina": "🇦🇷", "Colombia": "🇨🇴", "Uruguay": "🇺🇾",
    "Ecuador": "🇪🇨", "Chile": "🇨🇱", "Paraguay": "🇵🇾", "Peru": "🇵🇪",
    "Venezuela": "🇻🇪", "Bolivia": "🇧🇴", "Mexico": "🇲🇽", "United States": "🇺🇸",
    "USA": "🇺🇸", "Canada": "🇨🇦", "Costa Rica": "🇨🇷", "Honduras": "🇭🇳",
    "Panama": "🇵🇦", "Jamaica": "🇯🇲", "El Salvador": "🇸🇻", "Guatemala": "🇬🇹",
    "Trinidad and Tobago": "🇹🇹", "Haiti": "🇭🇹", "Cuba": "🇨🇺",
    "Curaçao": "🇨🇼",
    # Afrika
    "Nigeria": "🇳🇬", "South Africa": "🇿🇦", "Morocco": "🇲🇦", "Senegal": "🇸🇳",
    "Egypt": "🇪🇬", "Cameroon": "🇨🇲", "Ghana": "🇬🇭", "Ivory Coast": "🇨🇮",
    "Mali": "🇲🇱", "DR Congo": "🇨🇩", "Algeria": "🇩🇿", "Tunisia": "🇹🇳",
    "Tanzania": "🇹🇿", "Zambia": "🇿🇲", "Angola": "🇦🇴", "Uganda": "🇺🇬",
    "Gabon": "🇬🇦", "Mozambique": "🇲🇿", "Guinea": "🇬🇳", "Burkina Faso": "🇧🇫",
    "Cape Verde": "🇨🇻", "Equatorial Guinea": "🇬🇶", "Kenya": "🇰🇪",
    # Asien / Ozeanien
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Iran": "🇮🇷", "Australia": "🇦🇺",
    "Saudi Arabia": "🇸🇦", "Qatar": "🇶🇦", "Jordan": "🇯🇴", "Uzbekistan": "🇺🇿",
    "Iraq": "🇮🇶", "Indonesia": "🇮🇩", "China": "🇨🇳", "New Zealand": "🇳🇿",
    "Palestine": "🇵🇸", "Oman": "🇴🇲", "Bahrain": "🇧🇭", "Thailand": "🇹🇭",
    "India": "🇮🇳", "United Arab Emirates": "🇦🇪",
}

# ── WM-2026-Spielorte ─────────────────────────────────────────────────────────
# Schlüssel: frozenset({Heim, Gast}) – reihenfolgeunabhängig
# Tupel: (Stadionname, UTC-Offset im Sommer, exakt=True)
# Sommer-Offsets: EDT=-4  CDT=-5  MDT=-6  PDT=-7  MEX=-5  TOR=-4  VAN=-7
VENUES = {
    # Gruppe A  (Mexico · South Korea · Czech Republic · South Africa)
    frozenset({"Mexico", "South Africa"}):              ("SoFi Stadium, Los Angeles",            -7),
    frozenset({"South Korea", "Czech Republic"}):       ("MetLife Stadium, New York",            -4),
    frozenset({"Mexico", "South Korea"}):               ("AT&T Stadium, Dallas",                 -5),
    frozenset({"Czech Republic", "South Africa"}):      ("Gillette Stadium, Boston",             -4),
    frozenset({"Czech Republic", "Mexico"}):            ("AT&T Stadium, Dallas",                 -5),
    frozenset({"South Africa", "South Korea"}):         ("MetLife Stadium, New York",            -4),
    # Gruppe B  (Canada · Bosnia & Herzegovina · Qatar · Switzerland)
    frozenset({"Canada", "Bosnia & Herzegovina"}):      ("BMO Field, Toronto",                   -4),
    frozenset({"Qatar", "Switzerland"}):                ("Arrowhead Stadium, Kansas City",       -5),
    frozenset({"Canada", "Qatar"}):                     ("BC Place, Vancouver",                  -7),
    frozenset({"Switzerland", "Bosnia & Herzegovina"}): ("Arrowhead Stadium, Kansas City",       -5),
    frozenset({"Bosnia & Herzegovina", "Qatar"}):       ("BMO Field, Toronto",                   -4),
    frozenset({"Switzerland", "Canada"}):               ("BC Place, Vancouver",                  -7),
    # Gruppe C  (Brazil · Morocco · Haiti · Scotland)
    frozenset({"Brazil", "Morocco"}):                   ("MetLife Stadium, New York",            -4),
    frozenset({"Haiti", "Scotland"}):                   ("Hard Rock Stadium, Miami",             -4),
    frozenset({"Brazil", "Haiti"}):                     ("Hard Rock Stadium, Miami",             -4),
    frozenset({"Scotland", "Morocco"}):                 ("Lincoln Financial Field, Philadelphia",-4),
    frozenset({"Scotland", "Brazil"}):                  ("MetLife Stadium, New York",            -4),
    frozenset({"Morocco", "Haiti"}):                    ("Lincoln Financial Field, Philadelphia",-4),
    # Gruppe D  (USA · Paraguay · Australia · Turkey)
    frozenset({"USA", "Paraguay"}):                     ("Mercedes-Benz Stadium, Atlanta",       -4),
    frozenset({"Australia", "Turkey"}):                 ("Levi's Stadium, San Francisco",        -7),
    frozenset({"USA", "Australia"}):                    ("Lumen Field, Seattle",                 -7),
    frozenset({"Turkey", "Paraguay"}):                  ("Mercedes-Benz Stadium, Atlanta",       -4),
    frozenset({"Turkey", "USA"}):                       ("Levi's Stadium, San Francisco",        -7),
    frozenset({"Paraguay", "Australia"}):               ("NRG Stadium, Houston",                 -5),
    # Gruppe E  (Ivory Coast · Ecuador · Germany · Curaçao)
    frozenset({"Ivory Coast", "Ecuador"}):              ("Empower Field, Denver",                -6),
    frozenset({"Germany", "Curaçao"}):                  ("AT&T Stadium, Dallas",                 -5),
    frozenset({"Germany", "Ivory Coast"}):              ("Mercedes-Benz Stadium, Atlanta",       -4),
    frozenset({"Ecuador", "Curaçao"}):                  ("Empower Field, Denver",                -6),
    frozenset({"Curaçao", "Ivory Coast"}):              ("NRG Stadium, Houston",                 -5),
    frozenset({"Ecuador", "Germany"}):                  ("AT&T Stadium, Dallas",                 -5),
    # Gruppe F  (Netherlands · Japan · Sweden · Tunisia)
    frozenset({"Netherlands", "Japan"}):                ("Rose Bowl, Los Angeles",               -7),
    frozenset({"Sweden", "Tunisia"}):                   ("Allegiant Stadium, Las Vegas",         -7),
    frozenset({"Netherlands", "Sweden"}):               ("Rose Bowl, Los Angeles",               -7),
    frozenset({"Tunisia", "Japan"}):                    ("Allegiant Stadium, Las Vegas",         -7),
    frozenset({"Japan", "Sweden"}):                     ("SoFi Stadium, Los Angeles",            -7),
    frozenset({"Tunisia", "Netherlands"}):              ("SoFi Stadium, Los Angeles",            -7),
    # Gruppe G  (Saudi Arabia · Uruguay · Spain · Cape Verde)
    frozenset({"Saudi Arabia", "Uruguay"}):             ("Hard Rock Stadium, Miami",             -4),
    frozenset({"Spain", "Cape Verde"}):                 ("Lincoln Financial Field, Philadelphia",-4),
    frozenset({"Spain", "Saudi Arabia"}):               ("MetLife Stadium, New York",            -4),
    frozenset({"Uruguay", "Cape Verde"}):               ("Hard Rock Stadium, Miami",             -4),
    frozenset({"Cape Verde", "Saudi Arabia"}):          ("Lincoln Financial Field, Philadelphia",-4),
    frozenset({"Uruguay", "Spain"}):                    ("MetLife Stadium, New York",            -4),
    # Gruppe H  (Belgium · Egypt · New Zealand · Iran)
    frozenset({"Belgium", "Egypt"}):                    ("Estadio Akron, Guadalajara",           -5),
    frozenset({"Iran", "New Zealand"}):                 ("Estadio Azteca, Mexiko-Stadt",         -5),
    frozenset({"Belgium", "Iran"}):                     ("Estadio Azteca, Mexiko-Stadt",         -5),
    frozenset({"New Zealand", "Egypt"}):                ("Estadio Akron, Guadalajara",           -5),
    frozenset({"New Zealand", "Belgium"}):              ("Estadio BBVA, Monterrey",              -5),
    frozenset({"Egypt", "Iran"}):                       ("Estadio BBVA, Monterrey",              -5),
    # Gruppe I  (Iraq · Norway · France · Senegal)
    frozenset({"Iraq", "Norway"}):                      ("Estadio Azteca, Mexiko-Stadt",         -5),
    frozenset({"France", "Senegal"}):                   ("Estadio Akron, Guadalajara",           -5),
    frozenset({"France", "Iraq"}):                      ("Estadio Azteca, Mexiko-Stadt",         -5),
    frozenset({"Norway", "Senegal"}):                   ("Estadio Akron, Guadalajara",           -5),
    frozenset({"Norway", "France"}):                    ("Estadio BBVA, Monterrey",              -5),
    frozenset({"Senegal", "Iraq"}):                     ("Estadio BBVA, Monterrey",              -5),
    # Gruppe J  (Ghana · Panama · England · Croatia)
    frozenset({"Ghana", "Panama"}):                     ("NRG Stadium, Houston",                 -5),
    frozenset({"England", "Croatia"}):                  ("Gillette Stadium, Boston",             -4),
    frozenset({"England", "Ghana"}):                    ("Gillette Stadium, Boston",             -4),
    frozenset({"Panama", "Croatia"}):                   ("NRG Stadium, Houston",                 -5),
    frozenset({"Croatia", "Ghana"}):                    ("Arrowhead Stadium, Kansas City",       -5),
    frozenset({"Panama", "England"}):                   ("Arrowhead Stadium, Kansas City",       -5),
    # Gruppe K  (Argentina · Algeria · Austria · Jordan)
    frozenset({"Argentina", "Algeria"}):                ("Mercedes-Benz Stadium, Atlanta",       -4),
    frozenset({"Austria", "Jordan"}):                   ("Levi's Stadium, San Francisco",        -7),
    frozenset({"Argentina", "Austria"}):                ("Mercedes-Benz Stadium, Atlanta",       -4),
    frozenset({"Jordan", "Algeria"}):                   ("Levi's Stadium, San Francisco",        -7),
    frozenset({"Algeria", "Austria"}):                  ("SoFi Stadium, Los Angeles",            -7),
    frozenset({"Jordan", "Argentina"}):                 ("SoFi Stadium, Los Angeles",            -7),
    # Gruppe L  (Portugal · DR Congo · Uzbekistan · Colombia)
    frozenset({"Portugal", "DR Congo"}):                ("Gillette Stadium, Boston",             -4),
    frozenset({"Uzbekistan", "Colombia"}):              ("Lincoln Financial Field, Philadelphia",-4),
    frozenset({"Portugal", "Uzbekistan"}):              ("Gillette Stadium, Boston",             -4),
    frozenset({"Colombia", "DR Congo"}):                ("Lincoln Financial Field, Philadelphia",-4),
    frozenset({"Colombia", "Portugal"}):                ("MetLife Stadium, New York",            -4),
    frozenset({"DR Congo", "Uzbekistan"}):              ("MetLife Stadium, New York",            -4),
}


def get_flag(team_name):
    return FLAGS.get(team_name, "🏳")


def get_venue(home, away):
    """Gibt (stadium, utc_offset, approx) zurück.
    approx=True wenn kein exakter Spielortdatensatz vorhanden."""
    result = VENUES.get(frozenset({home, away}))
    if result:
        return result[0], result[1], False
    return "", -5, True   # Fallback: US Central Time


# ── Odds API ──────────────────────────────────────────────────────────────────
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

        stadium, tz_offset, tz_approx = get_venue(home, away)
        time_de = (commence + timedelta(hours=2)).strftime("%H:%M")   # MESZ = UTC+2
        time_local = (commence + timedelta(hours=tz_offset)).strftime("%H:%M")

        tips.append({
            "home": home,
            "away": away,
            "flag_home": get_flag(home),
            "flag_away": get_flag(away),
            "stadium": stadium,
            "time_de": time_de,
            "time_local": time_local,
            "tz_approx": tz_approx,
            "date": commence.strftime("%d.%m."),
            "time": time_de,
            "odds_1": round(o1, 2),
            "odds_x": round(ox, 2),
            "odds_2": round(o2, 2),
            "tip": result["recommended_tip"],
            "ev": result["recommended_ev"],
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
