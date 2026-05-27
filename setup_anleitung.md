# Setup-Anleitung — KickTipp WM 2026 Agent als Claude Project

## Voraussetzung
Claude Pro oder Team Account (Projects sind in der kostenlosen Version nicht verfügbar).

---

## Schritt-für-Schritt

### 1. Project anlegen
1. claude.ai öffnen, links in der Sidebar auf **„Projects"** klicken.
2. Oben rechts **„Create project"** (oder **„+ New Project"**) wählen.
3. **Name**: `KickTipp WM 2026 Agent`
4. **Description**: `EV-optimale Tipps für die FIFA WM 2026 in der KickTipp-Runde`

### 2. System Prompt einsetzen
1. Im neuen Project oben rechts auf **„Set custom instructions"** (oder das Stift-Symbol bei „Instructions").
2. Den **kompletten Inhalt von `system_prompt.md`** dort hineinkopieren.
3. Speichern.

### 3. Optimizer-Skript ins Knowledge laden
1. Im Project rechts auf **„Add content"** → **„Upload file"**.
2. `kicktipp_optimizer.py` auswählen und hochladen.
3. Sollte jetzt unter „Project knowledge" sichtbar sein.

### 4. Funktionstest mit Smoke-Query
Im Chat-Fenster des Projects schreiben:

> Lies einmal kicktipp_optimizer.py und bestätige, dass du die Funktionen analyze_match und run_batch kennst.

Erwartete Antwort: Agent listet die Funktionen und beschreibt kurz die Adjustment-Konvention.

### 5. End-to-End-Test
Eine echte Anfrage stellen:

> Was sind deine Tipps für die nächsten zwei WM-Spiele?

Der Agent sollte jetzt:
- den aktuellen Spielplan suchen,
- für jedes Spiel Quoten + Form + News holen,
- Lambda-Multiplikatoren begründen,
- den Optimizer im Code Interpreter ausführen,
- die Tipps mit Begründung präsentieren.

Falls einer dieser Schritte fehlt: System Prompt entsprechend nachschärfen.

### 6. Punkteregeln einpflegen (wenn klar)
Sobald die echten Punkteregeln deiner Tipprunde feststehen:
1. Öffne die System-Instruktionen des Projects.
2. Passe den Abschnitt „Punkteregeln der Tipprunde" an.
3. Falls die Regeln stark vom Standard abweichen (z.B. Bonusregelung für Außenseiter): auch `kicktipp_optimizer.py` updaten — Funktion `kicktipp_points` oder den `SCORING_RULES`-Dict.

---

## Typische Anfragen die jetzt funktionieren

- „Was sind deine Tipps für die nächsten zwei Tage?"
- „Welche Spiele kommen morgen, und was tippst du?"
- „Gib mir den Tipp für das Spiel Mexiko gegen Südafrika."
- „Heute ist KO-Phase — was empfiehlst du?"
- „Mein Tippplan hat 6 Spiele am Freitag, gib mir die Tipps mit Begründung."

---

## Wartung / Iteration

**Nach den ersten 5–10 Spielen** der WM:
- Tipps vs. tatsächliche Ergebnisse vergleichen
- Wenn Modell systematisch zu defensiv tippt (z.B. immer 1:0, tatsächlich oft 2:1): `rho` in `score_matrix()` von −0.12 Richtung −0.05 verschieben
- Wenn Modell die Adjustments zu stark setzt (Lambda-Multiplikatoren zu extrem): Faustregeln in System Prompt straffen

**Wenn dir Datenquellen fehlen**:
- Wettquoten-API hinzufügen (z.B. the-odds-api.com, Free Tier 500 Calls/Monat) — würde Tippstabilität erhöhen
- Eigene CSV mit historischen Spielen für Backtest

**Nächste Ausbaustufe (optional)**:
- MCP-Server bauen, der Spielplan + Quoten als strukturierte Tools liefert (statt Web Search)
- Telegram-Bot anbinden, der morgens automatisch die Tagestipps schickt
- Backtest-Modul gegen WM 2022 / EURO 2024

---

## Troubleshooting

| Problem | Lösung |
|---|---|
| Agent tippt aus dem Gedächtnis ohne zu suchen | System Prompt schärfen: „IMMER zuerst web_search aufrufen" deutlicher machen |
| Adjustments zu extrem (z.B. 1.5) | Im System Prompt das Band 0.80–1.20 nochmal explizit betonen |
| Code Interpreter wird nicht genutzt | Bei der ersten Frage explizit: „Nutze den Code Interpreter mit kicktipp_optimizer.py" |
| Quoten werden nicht gefunden | Liste in System Prompt mit deutschen Buchmachern erweitern (Oddset, Tipico, Bwin, Bet365, Interwetten) |
| Tipps wirken alle gleich (immer 1:0) | Das ist bei KickTipp-Standardregeln das mathematisch korrekte Ergebnis (siehe oben). Erst mit Bonusregeln für Außenseiter werden Tipps diverser. |
