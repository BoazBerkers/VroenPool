# WK2026 Match Predictor — Requirements Document
> Versie 1.0 · Familie VroenWK2026 pool · Juni 2026

---

## 1. Projectdoel

Een herbruikbaar CLI/web-tool dat voor **elke individuele wedstrijd** van het WK 2026 automatisch:

1. Actuele data ophaalt (odds, blessures, vorm, context)
2. De verwachte puntenopbrengst (Expected Value) berekent voor élk denkbaar scoreverloop
3. Een onderbouwde **aanbevolen uitslag** genereert, specifiek geoptimaliseerd voor het puntensysteem van de VroenWK2026 pool

Het resultaat: de gebruiker hoeft zelf **geen analyse te doen** — het tool geeft de beste voorspelling direct, inclusief uitleg.

---

## 2. Scope

### In scope (fase 1)
- Wedstrijdanalyse per match (op aanvraag, niet automatisch voor alle 104)
- EV-calculator op basis van Poisson-kansverdeling + marktodds
- Ophalen van odds, recente vorm en bekende blessures
- Strategieregel-engine (drie scenario's)
- Simpele web-UI of Streamlit-app

### Buiten scope (fase 2)
- Automatische push-notificaties bij blessure-updates
- Ranglijsttracking binnen de pool
- Automatisch invullen van de pool (scrapen van de poolwebsite)
- Mobiele app

---

## 3. Poolregels (hardcoded config)

Het puntensysteem is de kern van alle berekeningen en staat in een config-bestand.

```python
# config.py
SCORING = {
    "exact_score":        200,  # Beide teamscores exact goed
    "correct_draw":       100,  # Gelijkspel voorspeld + gelijkspel resultaat (elke score)
    "winner_plus_goals":   95,  # Winnaar goed + exact goals van 1 team
    "winner_only":         75,  # Alleen winnaar goed
    "one_team_goals":      20,  # Goals van 1 team exact goed (winnaar maakt niet uit)
    "nothing":              0,
}
BONUS = {
    "champion":          300,
    "topscorer":         300,  
}
```

---

## 4. Functionele requirements

### FR-01 — Wedstrijdselectie
- De gebruiker kan een wedstrijd selecteren uit het volledige WK-schema
- Het schema is hardcoded in `schedule.py` als lijst van dicts:
  ```python
  {"id": 1, "date": "2026-06-11T21:00Z", "team_a": "Mexico", "team_b": "Zuid-Afrika", "group": "A"}
  ```
- De UI toont standaard de **eerstvolgende wedstrijd** (op basis van huidige tijd)
- Wedstrijden zijn filterbaar op: groepsfase / knock-out, of te spelen in <24h

### FR-02 — Data ophalen
Per geselecteerde wedstrijd haalt het tool op:

| Databron | Inhoud | API |
|----------|--------|-----|
| Odds | Win/Gelijkspel/Win kansen + Over/Under doelpunten | The Odds API |
| Teamselectie / blessures | Ontbrekende spelers, twijfelgevallen | API-Football of web scrape |
| Recente vorm | Laatste 5 interlands per team (W/D/L + doelpunten) | API-Football |
| Head-to-head | Laatste 5 onderlinge duels | API-Football |
| Toernooicontext | Groepsstand (als beschikbaar), eliminatiescenario's | API-Football of berekend |

Alle API-responses worden **gecached per wedstrijd** (TTL: 30 minuten) in een lokale JSON-file om rate limits te sparen.

### FR-03 — EV-calculator
Het hart van het tool. Berekent voor elke mogelijke voorspelling (0-0 t/m 5-5) de verwachte puntenopbrengst.

**Input:**
- Odds → omgezet naar kansen per uitslag via Poisson-model
- Score-matrix: `P(score = x-y)` voor alle x, y van 0 t/m 5

**Algoritme:**

```python
def calculate_points(pred_a, pred_b, res_a, res_b) -> int:
    a, b = pred_a, pred_b
    x, y = res_a, res_b

    if a == x and b == y:              return 200  # exact
    if a == b and x == y:              return 100  # gelijkspel-anker
    
    winner_correct = (a > b and x > y) or (a < b and x < y)
    if winner_correct and (a == x or b == y): return 95  # winnaar + 1 team goals
    if winner_correct:                         return 75  # alleen winnaar
    if a == x or b == y:                       return 20  # 1 team goals consolatie
    return 0

def expected_value(pred_a, pred_b, score_matrix) -> float:
    return sum(
        prob * calculate_points(pred_a, pred_b, x, y)
        for (x, y), prob in score_matrix.items()
    )

def best_prediction(score_matrix) -> tuple[int, int, float]:
    """Geeft de (pred_a, pred_b, max_ev) terug."""
    best = max(
        ((a, b, expected_value(a, b, score_matrix))
         for a in range(6) for b in range(6)),
        key=lambda t: t[2]
    )
    return best
```

**Poisson score-matrix bouwen:**
```python
from scipy.stats import poisson
import numpy as np

def build_score_matrix(lambda_a: float, lambda_b: float, max_goals=5) -> dict:
    """
    lambda_a = verwacht doelpunten team A
    lambda_b = verwacht doelpunten team B
    Afgeleid van odds via Dixon-Coles of direct van over/under
    """
    matrix = {}
    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            matrix[(x, y)] = poisson.pmf(x, lambda_a) * poisson.pmf(y, lambda_b)
    return matrix
```

**Lambda's afleiden uit odds:**
- Over/Under 2.5 odds → totaal verwachte goals (bijv. 2.4)
- Win-kansen → thuisvoordeel factor → lambda_a / lambda_b split
- Zie `dixon_coles.py` of simpele schaling als benadering

### FR-04 — Strategieregel-engine
Naast de wiskundige EV is er een laag met domeinkennis die de aanbeveling kan aanpassen:

```python
def apply_strategy_rules(pred, team_a, team_b, odds, injuries, context) -> Prediction:
```

**Regel 1 — "Nul-houden hefboom"**
Trigger: winnaarskans favoriet > 75% EN underdog heeft duidelijk zwakkere aanval
→ Overrule naar de EV-optimale score waarbij de underdog 0 goals heeft (bijv. 2-0, 3-0)
→ Reden: elke win waarbij de underdog niet scoort geeft 95 pts ipv 75

**Regel 2 — "Gelijkspel-anker"**
Trigger: winstkansen liggen tussen 35-45% voor beide teams (coin-flip)
→ Forceer 1-1 als aanbeveling
→ Reden: bij elk gelijkspel 100 pts, bij 1-1 exact zelfs 200 pts; consolatieprijs 20 pts bij veel uitkomsten

**Regel 3 — "Blessure-aanpassing"**
Trigger: sterspeler (aanvaller / creatief middenveld) van favoriet afwezig
→ Verlaag lambda_a met 10-20% → herbereken score-matrix

**Regel 4 — "Late groepswedstrijd-risico"**
Trigger: beide teams al geplaatst voor knock-outs in matchday 3
→ Flag: "let op — rotatie-opstellingen verwacht" → aanbeveling bewust conservatiever (lage score)

**Regel 5 — "Hoogtenadeel"**
Trigger: stadion > 1500m hoogte én een van de teams speelt er niet normaal
→ Verlaag verwachte doelpunten met ~15%, neigt naar 0-0 / 1-0

### FR-05 — Output / Aanbeveling
Per wedstrijd geeft het tool:

```
┌─────────────────────────────────────────────────┐
│ MEXICO vs ZUID-AFRIKA                           │
│ 11 jun 2026 · 21:00 · Groep A                  │
├─────────────────────────────────────────────────┤
│ 🎯 AANBEVOLEN VOORSPELLING: 2-0                 │
│ Strategie: Nul-houden hefboom                   │
│ Verwachte punten: 84.3 EV                       │
├─────────────────────────────────────────────────┤
│ ODDS                    CONTEXT                 │
│ Mexico win   68%        Hoogte: 2.240m          │
│ Gelijkspel   19%        Vorm Mexico: W W W D W  │
│ Z-Afrika win 13%        Blessures: geen bekend  │
│ O/U 2.5: -140 Under                             │
├─────────────────────────────────────────────────┤
│ TOP 5 ALTERNATIEVEN      EV      VERSCHIL       │
│ 1-0                      81.2    -3.1 pts       │
│ 2-1                      76.8    -7.5 pts       │
│ 3-0                      74.1    -10.2 pts      │
│ 1-1 (gelijkspel-anker)  58.4    -25.9 pts      │
└─────────────────────────────────────────────────┘
```

Verplichte output-velden:
- Aanbevolen score (duidelijk, groot)
- Strategie-naam + 1-zin uitleg
- EV van de aanbeveling
- Odds samenvatting
- Top 3-5 alternatieven met EV-verschil
- Blessure-waarschuwingen (rood als kritiek)
- Contextfactoren (hoogte, thuisspelend land, etc.)

### FR-06 — Interactiviteit
- Gebruiker kan de aanbeveling **manueel overschrijven** en dan de EV zien
- "Refresh data" knop om cache te vernieuwen
- "Kopieer" knop om voorspelling naar clipboard te kopiëren
- Tijdsindicator: "Data bijgewerkt X minuten geleden"

---

## 5. Data Sources & APIs

### 5.1 The Odds API
- URL: `https://api.the-odds-api.com/`
- Endpoint: `/v4/sports/soccer_fifa_world_cup/odds`
- Parameters: `regions=eu&markets=h2h,totals&oddsFormat=decimal`
- Gratis tier: 500 requests/maand (meer dan genoeg voor 104 wedstrijden)
- Sleutel: `ODDS_API_KEY` in `.env`
- Caching: sla op als `cache/odds_{match_id}_{timestamp}.json`

### 5.2 API-Football
- URL: `https://api-football-v1.p.rapidapi.com/v3/`
- Endpoints:
  - `/teams/statistics` — teamvorm
  - `/fixtures/headtohead` — onderlinge duels
  - `/players/squads` — selectie (voor blessure-context)
  - `/injuries` — blessurerapport per wedstrijd (zodra FIFA-ID beschikbaar)
- Gratis tier: 100 requests/dag
- Caching: TTL 6 uur voor historische data, 30 min voor blessures

### 5.3 Fallback: Claude API (web search)
Voor actuele blessure-updates die niet in de API staan:
```python
def fetch_injury_news(team_name: str) -> str:
    """Vraag Claude om het web te doorzoeken naar recente blessurenieuws."""
    # Gebruik Anthropic API met web_search tool
    # Prompt: "Zijn er blessures of twijfelgevallen in de selectie van {team_name} voor het WK 2026? 
    #          Geef alleen bevestigde afwezigen en twijfelgevallen."
```

### 5.4 Lokaal schema-bestand
`data/schedule.json` — het volledige WK-schema (hardcoded uit de poolpagina)
Bevat: datum, teams, groep, wedstrijd-ID, stadion, hoogte (m)

---

## 6. UI Requirements

### Technologie: Streamlit (aanbevolen)
```bash
pip install streamlit scipy requests python-dotenv
streamlit run app.py
```

Werkt direct in GitHub Codespaces via port-forwarding. Geen aparte frontend nodig.

### Schermindeling (single-page)
```
┌──────────────────────────────────────────────────┐
│ [Header] WK2026 Predictor               [Refresh]│
├──────────────────────────────────────────────────┤
│ WEDSTRIJDSELECTIE                                │
│ [Dropdown: selecteer wedstrijd]                  │
│ [Filter: Groep A ▼] [Volgende 24h] [Alle]       │
├──────────────────────────────────────────────────┤
│ WEDSTRIJD-ANALYSE                                │
│ [Links: team A]    VS    [Rechts: team B]        │
│                                                  │
│ AANBEVELING: 2-0 (groot, opvallend)             │
│ Strategie: Nul-houden hefboom                   │
│                                                  │
│ [Odds kolom]  [Blessures kolom]  [Vorm kolom]   │
│                                                  │
│ EV TABEL: alle scores 0-0 t/m 4-4 als heatmap  │
│                                                  │
│ [Alternatieve voorspellingen top 5]              │
│                                                  │
│ [Manuele invoer: score X - Y → bereken EV]      │
└──────────────────────────────────────────────────┘
```

### UI-elementen (verplicht)
- Aanbeveling: grote, gekleurde metric (`st.metric`)
- EV heatmap: `st.dataframe` met kleur-coding (groen = hoge EV)
- Blessure-lijst: rood als sterspeler ontbreekt
- Kopieerknop: `st.code(f"{a}-{b}", language=None)` of clipboard JS
- Data timestamp: `st.caption(f"Bijgewerkt: {cache_time}")`

---

## 7. Projectstructuur

```
wk2026-predictor/
├── app.py                 # Streamlit entry point
├── config.py              # Puntensysteem config
├── schedule.py            # Volledig WK-schema
├── data/
│   └── schedule.json      # Wedstrijdschema JSON
├── modules/
│   ├── data_fetcher.py    # API calls (odds, vorm, blessures)
│   ├── cache.py           # JSON file-based cache
│   ├── poisson.py         # Score-matrix via Poisson
│   ├── ev_calculator.py   # EV berekening (kern)
│   ├── strategy.py        # Strategieregels
│   └── injury_llm.py      # Claude API fallback voor nieuws
├── tests/
│   ├── test_ev.py         # Unit tests voor puntentelling
│   └── test_poisson.py
├── .env.example           # API keys template
├── requirements.txt
└── README.md
```

---

## 8. Non-functionele requirements

| Aspect | Eis |
|--------|-----|
| Snelheid | Resultaat binnen 10 seconden (inclusief gecachte data) |
| Beschikbaarheid | Lokaal draaien in Codespaces; geen uptime-eis |
| Herbruikbaarheid | Werkt voor elke wedstrijd in het schema, inclusief knock-out |
| Configureerbaar | Puntensysteem volledig instelbaar via `config.py` |
| Offline-modus | Werkt met gecachte data als APIs niet bereikbaar zijn |
| Testbaarheid | `test_ev.py` dekt alle puntentelling-varianten (min. 20 testcases) |
| API-zuinigheid | Max 5 API-calls per wedstrijd (dankzij caching) |

---

## 9. Vereiste testcases voor EV-calculator

Verificatiegevallen die altijd moeten slagen:

```python
# EXACT
assert calculate_points(2,1, 2,1) == 200
assert calculate_points(1,1, 1,1) == 200  # exact overrulet gelijkspel

# GELIJKSPEL-ANKER
assert calculate_points(1,1, 0,0) == 100  # gelijkspel, andere score
assert calculate_points(1,1, 2,2) == 100
assert calculate_points(0,0, 3,3) == 100
assert calculate_points(2,2, 1,1) == 100

# WINNAAR + 1 TEAM GOALS
assert calculate_points(2,0, 3,0) == 95   # B=0 klopt, A wint
assert calculate_points(2,0, 2,1) == 95   # A=2 klopt, A wint
assert calculate_points(0,2, 1,2) == 95   # B=2 klopt, B wint
assert calculate_points(3,1, 3,2) == 95   # A=3 klopt, A wint

# ALLEEN WINNAAR
assert calculate_points(3,1, 1,0) == 75   # A wint, geen goals exact
assert calculate_points(0,2, 0,1) == 75   # B wint, maar B goals: 2≠1

# ÉÉN TEAM GOALS (consolatie)
assert calculate_points(1,2, 1,0) == 20   # A=1 klopt, maar winnaar fout
assert calculate_points(2,0, 3,2) == 20   # B=0≠2 nee, A=2≠3 nee... wacht
# Let op: A=2 voorspeld, A=3 gescoord → geen match; B=0 voorspeld, B=2 gescoord → geen match
# Maar A wint in beide! → winner correct = 75 pts
assert calculate_points(2,0, 3,2) == 75   # correctie: A wint in beide gevallen

# NIKS
assert calculate_points(2,1, 0,3) == 0    # alles fout
assert calculate_points(1,0, 2,2) == 20   # A=1≠2, B=0≠2... of toch 0?
# B=0 voorspeld, B scoort 2 → geen match. A=1 voorspeld, A scoort 2 → geen match. → 0
```

---

## 10. Knock-outfase aanpassing

Zodra de 16de finales en verder beginnen, veranderen de teams per wedstrijd. Het schema vermeldt dan "Winnaar A2 vs Winnaar B2" etc.

- `schedule.py` moet een `resolve_teams()` functie hebben die na de groepsfase de daadwerkelijke teams invult op basis van groepsresultaten
- Alternatief: gebruiker typt zelf de teamnamen in na bekendmaking
- Odds-API haalt automatisch de juiste match op zodra teams bekend zijn (op basis van `sport_event_id`)

---

## 11. Stappenplan voor vibe-coding (aanbevolen volgorde)

```
Stap 1: Bouw ev_calculator.py + tests
        → Geen externe dependencies, puur algoritme
        → Testcases bovenaan dit document geven directe verificatie

Stap 2: Bouw poisson.py
        → Scipy + formule om van odds naar lambda_a/lambda_b te gaan
        → Test met bekende wedstrijden (bijv. Duitsland-Curaçao: hoge lambda_a)

Stap 3: Bouw data_fetcher.py + cache.py
        → Eerst hardcoded mock-data, daarna echte API-calls
        → .env met ODDS_API_KEY en RAPIDAPI_KEY

Stap 4: Bouw strategy.py
        → De 5 strategieregels als aparte functies
        → Input: odds, blessures, context → output: aanbevolen score + reden

Stap 5: Bouw app.py (Streamlit UI)
        → Eerst minimalistische UI met dropdown + aanbeveling
        → Daarna uitbreiden met heatmap, alternatieven, etc.

Stap 6: Voeg schedule.py toe met volledig WK-schema
        → Datum-filtering voor "volgende wedstrijd"
        → Groep-labels voor context
```

---

## 12. Copilot-prompts om mee te starten

Plak deze direct in GitHub Copilot Chat:

**Voor ev_calculator.py:**
```
Create a Python module ev_calculator.py with:
1. A function calculate_points(pred_a, pred_b, res_a, res_b) -> int
   using this scoring system: exact=200, correct_draw=100, winner+one_team_goals=95, 
   winner_only=75, one_team_goals=20, nothing=0.
   A "correct draw" means: predicted draw (pred_a==pred_b) AND result is draw (res_a==res_b).
2. A function expected_value(pred_a, pred_b, score_matrix: dict) -> float
   where score_matrix is {(x,y): probability} for all result scores.
3. A function best_prediction(score_matrix) -> tuple[int, int, float]
   returning the (pred_a, pred_b, ev) that maximizes expected_value.
Include docstrings and type hints.
```

**Voor poisson.py:**
```
Create a Python module poisson.py with:
1. A function build_score_matrix(lambda_a, lambda_b, max_goals=5) -> dict
   using scipy.stats.poisson to calculate P(score=x-y) for all x,y in [0..max_goals].
2. A function odds_to_lambdas(win_prob_a, draw_prob, win_prob_b, total_goals_estimate) 
   -> tuple[float, float]
   that estimates expected goals per team using Poisson-based calibration.
   Use the Dixon-Coles approach or a simple scaled method.
Include docstrings and type hints.
```

**Voor app.py:**
```
Create a Streamlit app app.py for a WK 2026 match predictor.
It should:
1. Show a selectbox to choose an upcoming match from a schedule list.
2. Display odds, form, and injury info in 3 columns.
3. Show the recommended prediction prominently using st.metric.
4. Show an EV heatmap using st.dataframe with background_gradient for scores 0-0 to 4-4.
5. List top 5 alternative predictions with their EV.
6. Add a manual score input to calculate EV for any custom prediction.
Import ev_calculator, poisson, strategy, and data_fetcher modules.
```