"""
KickTipp EV-Optimizer (Agent Version)
=====================================
Erweiterte Version mit Adjustment-Hooks für den Live-Daten-Workflow.

Verwendung durch den Agent:
    from kicktipp_optimizer import analyze_match, run_batch, SCORING_RULES

    matches = [
        {
            "home": "Mexiko",
            "away": "Suedafrika",
            "odds": (1.46, 3.80, 5.75),
            "lambda_home_mult": 1.05,   # Heim staerker als Markt (z.B. Form)
            "lambda_away_mult": 0.90,   # Gast schwaecher (z.B. Ausfaelle)
            "rationale": "Suedafrika ohne Hauptstuermer; Mexiko 4-Spiele-Heimserie"
        },
        ...
    ]
    results = run_batch(matches)

Adjustment-Konvention:
    1.0  = Markt akzeptieren (Default)
    >1.0 = Team performt staerker als Quote impliziert
    <1.0 = Team schwaecher als Quote impliziert
    Normal: 0.80 - 1.20. Ausserhalb nur mit starker Begruendung.
"""

import math
import numpy as np


def _poisson_pmf(k, mu):
    """Poisson PMF via log-gamma — works for scalar k or 1-D numpy array."""
    if np.isscalar(k):
        if mu <= 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(-mu + k * math.log(mu) - math.lgamma(k + 1))
    k = np.asarray(k, dtype=float)
    out = np.zeros_like(k)
    if mu > 0:
        out = np.exp(-mu + k * math.log(mu) - np.array([math.lgamma(ki + 1) for ki in k]))
    else:
        out[k == 0] = 1.0
    return out


# ----- Konfigurierbare Punkteregeln -----
# Wird vom Agent ueberschrieben sobald die echten Regeln der Tipprunde feststehen.
SCORING_RULES = {
    "exact":     4,   # Exaktes Ergebnis
    "goal_diff": 3,   # Korrekte Tordifferenz (nur bei Sieg)
    "tendency":  2,   # Korrekte Tendenz (1/X/2)
    "wrong":     0,
}


# ----- 1. Quoten -> Wahrscheinlichkeiten -----
def odds_to_probs(odds_1, odds_x, odds_2):
    """Decimal Odds -> no-vig Wahrscheinlichkeiten."""
    raw = np.array([1.0 / odds_1, 1.0 / odds_x, 1.0 / odds_2])
    return raw / raw.sum()


# ----- 2. P(1X2) -> erwartete Tore -----
def expected_goals_from_probs(p_home, p_draw, p_away, max_goals=10):
    """Finde (lambda_home, lambda_away), die zur 1X2-Verteilung passen.
    Zweistufige Gittersuche ersetzt scipy.optimize (kein scipy noetig)."""
    k = np.arange(max_goals + 1)

    def loss(lh, la):
        ph = _poisson_pmf(k, lh)
        pa = _poisson_pmf(k, la)
        m = np.outer(ph, pa)
        return (
            (np.tril(m, -1).sum() - p_home) ** 2
            + (np.diag(m).sum() - p_draw) ** 2
            + (np.triu(m, 1).sum() - p_away) ** 2
        )

    # Grobe Suche
    best = (1e9, 1.4, 1.1)
    for lh in np.arange(0.3, 4.1, 0.1):
        for la in np.arange(0.3, 3.1, 0.1):
            v = loss(lh, la)
            if v < best[0]:
                best = (v, lh, la)

    # Feine Suche im besten Bereich
    lh0, la0 = best[1], best[2]
    for lh in np.arange(max(0.1, lh0 - 0.15), lh0 + 0.16, 0.01):
        for la in np.arange(max(0.1, la0 - 0.15), la0 + 0.16, 0.01):
            v = loss(lh, la)
            if v < best[0]:
                best = (v, lh, la)

    return best[1], best[2]


# ----- 3. Dixon-Coles Score-Matrix -----
def dc_correction(i, j, lh, la, rho):
    if i == 0 and j == 0: return 1 - lh * la * rho
    if i == 0 and j == 1: return 1 + lh * rho
    if i == 1 and j == 0: return 1 + la * rho
    if i == 1 and j == 1: return 1 - rho
    return 1.0


def score_matrix(lh, la, max_goals=8, rho=-0.12):
    m = np.zeros((max_goals + 1, max_goals + 1))
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            m[i, j] = (
                _poisson_pmf(i, lh)
                * _poisson_pmf(j, la)
                * dc_correction(i, j, lh, la, rho)
            )
    return m / m.sum()


# ----- 4. KickTipp-Punkte (konfigurierbar) -----
def kicktipp_points(tip_h, tip_a, real_h, real_a, scoring=None):
    s = scoring or SCORING_RULES
    if tip_h == real_h and tip_a == real_a:
        return s["exact"]
    tip_diff = tip_h - tip_a
    real_diff = real_h - real_a
    if np.sign(tip_diff) != np.sign(real_diff):
        return s["wrong"]
    if tip_diff == real_diff and tip_diff != 0:
        return s["goal_diff"]
    return s["tendency"]


# ----- 5. EV-Grid ueber alle Tipps -----
def expected_value_grid(matrix, max_tip=5, scoring=None):
    ev = np.zeros((max_tip + 1, max_tip + 1))
    rows = matrix.shape[0]
    for th in range(max_tip + 1):
        for ta in range(max_tip + 1):
            total = 0.0
            for rh in range(rows):
                for ra in range(rows):
                    p = matrix[rh, ra]
                    if p < 1e-9:
                        continue
                    total += p * kicktipp_points(th, ta, rh, ra, scoring)
            ev[th, ta] = total
    return ev


# ----- 6. Hauptfunktion -----
def analyze_match(
    home,
    away,
    odds,
    lambda_home_mult=1.0,
    lambda_away_mult=1.0,
    rationale="",
    scoring=None,
    verbose=True,
):
    """
    Liefert EV-optimalen Tipp plus Alternativen.

    Parameters
    ----------
    home, away : str
    odds : tuple (float, float, float) -- (1, X, 2)
    lambda_home_mult, lambda_away_mult : float
        Multiplikatoren auf marktimpliziertes lambda. 1.0 = Markt unveraendert.
    rationale : str
        Begruendung der Adjustments (geht in Output).
    scoring : dict or None
        Falls None -> SCORING_RULES.
    verbose : bool
        Print-Ausgabe.
    """
    if scoring is None:
        scoring = SCORING_RULES

    o1, ox, o2 = odds
    p_h, p_d, p_a = odds_to_probs(o1, ox, o2)
    lh_base, la_base = expected_goals_from_probs(p_h, p_d, p_a)

    lh = lh_base * lambda_home_mult
    la = la_base * lambda_away_mult

    matrix = score_matrix(lh, la)
    ev = expected_value_grid(matrix, scoring=scoring)

    flat = [(ev[i, j], i, j) for i in range(ev.shape[0]) for j in range(ev.shape[1])]
    flat.sort(reverse=True)
    top_tips = [{"score": f"{h}:{a}", "ev": round(e, 3)} for e, h, a in flat[:5]]

    msmall = matrix[:6, :6]
    probs = [(msmall[i, j], i, j) for i in range(6) for j in range(6)]
    probs.sort(reverse=True)
    top_outcomes = [{"score": f"{h}:{a}", "prob": round(p, 4)} for p, h, a in probs[:5]]

    gap = top_tips[0]["ev"] - top_tips[1]["ev"]
    close_call = gap < 0.05

    result = {
        "match": f"{home} - {away}",
        "odds": {"1": o1, "X": ox, "2": o2},
        "implied_probs": {"1": round(p_h, 3), "X": round(p_d, 3), "2": round(p_a, 3)},
        "lambdas_base": {home: round(lh_base, 2), away: round(la_base, 2)},
        "lambdas_adjusted": {home: round(lh, 2), away: round(la, 2)},
        "adjustments": {"home_mult": lambda_home_mult, "away_mult": lambda_away_mult},
        "rationale": rationale,
        "top_tips": top_tips,
        "top_outcomes": top_outcomes,
        "recommended_tip": top_tips[0]["score"],
        "recommended_ev": top_tips[0]["ev"],
        "close_call": close_call,
        "ev_gap_to_second": round(gap, 3),
    }

    if verbose:
        _print_result(result)
    return result


def _print_result(r):
    print(f"\n{'=' * 64}")
    print(f"{r['match']}")
    print(f"{'=' * 64}")
    print(f"Quoten: 1={r['odds']['1']}  X={r['odds']['X']}  2={r['odds']['2']}")
    print(f"Impl.Wahrsch.: 1={r['implied_probs']['1']:.1%}  X={r['implied_probs']['X']:.1%}  2={r['implied_probs']['2']:.1%}")
    home, away = list(r['lambdas_base'].keys())
    print(f"Lambdas (Markt):     {home} {r['lambdas_base'][home]} - {away} {r['lambdas_base'][away]}")
    if r["adjustments"]["home_mult"] != 1.0 or r["adjustments"]["away_mult"] != 1.0:
        print(f"Lambdas (angepasst): {home} {r['lambdas_adjusted'][home]} - {away} {r['lambdas_adjusted'][away]}")
        print(f"  Adjustments: home x{r['adjustments']['home_mult']}, away x{r['adjustments']['away_mult']}")
        print(f"  Begruendung: {r['rationale']}")
    print(f"\nTop-5 EV-Tipps:")
    for t in r["top_tips"]:
        print(f"  {t['score']:<6}  EV {t['ev']}")
    flag = "  [KNAPP - Alternative pruefen]" if r["close_call"] else ""
    print(f"\nEMPFEHLUNG: {r['recommended_tip']}  (EV {r['recommended_ev']}){flag}")


def run_batch(matches, scoring=None):
    """Mehrere Spiele in einem Rutsch verarbeiten."""
    results = []
    for m in matches:
        if scoring is not None and "scoring" not in m:
            m = {**m, "scoring": scoring}
        results.append(analyze_match(**m))

    print(f"\n{'=' * 64}")
    print("ZUSAMMENFASSUNG")
    print(f"{'=' * 64}")
    print(f"{'Spiel':<38} {'Tipp':<8} {'EV':<6}  {'Hinweis'}")
    for r in results:
        note = "knapp - Alternative pruefen" if r["close_call"] else ""
        print(f"{r['match']:<38} {r['recommended_tip']:<8} {r['recommended_ev']:<6}  {note}")
    return results


# ----- Demo -----
if __name__ == "__main__":
    print("DEMO: WM 2026, 1. Spieltag - mit beispielhaften Adjustments\n")
    matches = [
        {
            "home": "Mexiko", "away": "Suedafrika",
            "odds": (1.46, 3.80, 5.75),
            "rationale": "Keine Adjustments (Demo)",
        },
        {
            "home": "Suedkorea", "away": "Tschechien",
            "odds": (2.60, 3.25, 2.70),
            "lambda_home_mult": 1.10,
            "lambda_away_mult": 0.90,
            "rationale": "Beispiel: Korea letzte 5 Spiele 2.2 Tore/Spiel, Tschechien ohne Stuermer X",
        },
        {
            "home": "Kanada", "away": "Bosnien-Herzegowina",
            "odds": (1.83, 3.60, 4.20),
            "rationale": "Keine Adjustments (Demo)",
        },
        {
            "home": "USA", "away": "Paraguay",
            "odds": (1.93, 3.20, 3.40),
            "lambda_home_mult": 0.95,
            "rationale": "Beispiel: USA-Heimserie verhalten, defensiver Stil",
        },
    ]
    run_batch(matches)
