# WK2026 Match Predictor

A comprehensive World Cup 2026 match prediction tool for the VroenWK2026 family pool. Generates data-driven score recommendations optimized to maximize points using mathematical expected value (EV) calculations.

## Features

- **EV-Optimized Predictions**: Uses Poisson distribution to calculate the best possible prediction for each match
- **Live Data Integration**: Pulls odds, injury info, and team form from external APIs (with mock data for testing)
- **5 Strategy Rules**: Domain-specific rules that adjust predictions based on context (strong favorites, altitude, injuries, etc.)
- **Interactive Streamlit UI**: Web-based interface with heatmaps, alternatives, and manual testing
- **Smart Caching**: Caches API responses to respect rate limits (30 min for odds, 6h for historical)
- **Comprehensive Tests**: 26+ unit tests covering all scoring scenarios

## Installation

```bash
# Clone/download the repository
cd VroenPool

# Install dependencies
pip install -r requirements.txt
```

## Setup

### 1. Configure API Keys (Optional)

If you want to use real APIs instead of mock data, create a `.env` file:

```bash
cp .env.example .env
# Edit .env with your API keys:
# ODDS_API_KEY=your_key_here
# RAPIDAPI_KEY=your_key_here
```

### 2. Add Your WK2026 Schedule (Optional)

The tool comes with sample matches. To use your full schedule from the pool website:

1. Export your pool's fixture list as JSON
2. Place it at `data/schedule.json`
3. The app will auto-load it on startup

## Usage

### Run the Streamlit App

```bash
streamlit run app.py
```

Then open your browser to: **http://localhost:8501**

### Select a Match

1. Use the sidebar dropdown to pick a match
2. The app displays:
   - **Recommended prediction** (highlighted in green)
   - **Odds, injuries, and recent form** (3-column layout)
   - **EV heatmap** showing all predictions (0-0 to 5-5)
   - **Top 5 alternatives** ranked by expected value
   - **Manual tester** to check EV for any custom score

### Run Tests

```bash
# Run all unit tests
pytest tests/test_ev.py -v

# Run specific test
pytest tests/test_ev.py::TestCalculatePoints::test_exact_score -v
```

## Architecture

### Core Modules

| Module | Purpose |
|--------|---------|
| `config.py` | Pool scoring system (200 pts for exact, 100 for draw, etc.) |
| `modules/ev_calculator.py` | Core math: calculate points, EV, optimize predictions |
| `modules/poisson.py` | Poisson score distributions & odds conversion |
| `modules/data_fetcher.py` | Fetch odds, injuries, form (mock + real APIs) |
| `modules/cache.py` | File-based JSON cache with TTL |
| `modules/strategy.py` | 5 strategy rules for adjusting predictions |
| `schedule.py` | WK2026 match schedule & filtering |
| `app.py` | Streamlit UI orchestrator |

### Data Flow

```
Schedule → Select Match
    ↓
Data Fetcher (odds, injuries, form)
    ↓
Odds → Lambdas (expected goals per team)
    ↓
Build Score Matrix (Poisson)
    ↓
Calculate EV for all predictions (0-0 to 5-5)
    ↓
Find best prediction (max EV)
    ↓
Apply Strategy Rules (nul-houden, draw-anchor, etc.)
    ↓
Render UI with heatmap & alternatives
```

## Scoring System

The VroenWK2026 pool uses this scoring:

- **Exact Score**: 200 pts (2-1 = 2-1)
- **Correct Draw**: 100 pts (predict 1-1, any draw result)
- **Winner + 1 Team Goals**: 95 pts (winner correct + one team's goals exact)
- **Winner Only**: 75 pts (just the winner was correct)
- **One Team Goals**: 20 pts (one team's goals exact, winner irrelevant)
- **Nothing**: 0 pts

## Strategy Rules

### Rule 1: Nul-houden Hefboom
If favorite has >75% win odds AND underdog has weak attack (missing key attackers), force underdog to 0 goals.
Example: 2-1 → 2-0 (gives 95 pts on a 2-0 result instead of 75).

### Rule 2: Gelijkspel-anker
If both teams have 35-45% win odds (coin flip), recommend 1-1.
Reasoning: 100 pts on any draw + potential 200 pts on 1-1 exact.

### Rule 3: Blessure-aanpassing
If a star attacker or creative midfielder is missing, reduce expected goals by 10-20%.

### Rule 4: Late Groupstage Risk
If both teams are already qualified (matchday 3), flag conservative prediction (rotation risk).

### Rule 5: Hoogte-nadeel
If stadium altitude > 1500m, reduce expected goals by ~15%.

## Example Output

For **Netherlands vs Japan** (from wireframe):

```
RECOMMENDED PREDICTION: 2-0
Strategy: Nul-houden hefboom (Japan weak attack, missing Mitoma & Minamino)
Expected Value: 84.3 pts

Odds: NL 53%, Draw 26%, Japan 21% | O/U 2.5: Under
Recent Form: NL WWDWW (avg 2.0 goals) | JP WWWLW (avg 1.8 goals)
Injuries: NL: Simons, De Ligt (D) | JP: Mitoma, Minamino (F)

TOP ALTERNATIVES:
1. 1-0     EV: 81.2  (-3.1 pts)
2. 2-1     EV: 76.8  (-7.5 pts)
3. 3-0     EV: 74.1  (-10.2 pts)
4. 1-1     EV: 58.4  (-25.9 pts)
```

## Testing

### Unit Tests (26 passing)

- **calculate_points()**: All 6 scoring rules (exact, draw, winner+goals, winner, consolation)
- **expected_value()**: Mixed outcomes, draw anchors, worse predictions
- **best_prediction()**: Single outcome, multiple outcomes, coin-flip scenarios
- **Poisson matrix**: Probability sums, dimensions, lambda relationships
- **odds_to_lambdas()**: Conversion, strong favorites, underdogs, symmetric scenarios
- **Integration**: Full pipeline (deutschland vs curacao, netherlands vs japan)

Run: `pytest tests/test_ev.py -v`

### Integration Tests (Planned)

- Mock API responses
- Full pipeline end-to-end
- Strategy rules triggering correctly

## Cache Management

Cache is stored in `cache/` directory with 30-min TTL for live odds, 6h for historical data.

To clear cache:

```python
from modules.cache import cache_clear
cache_clear()  # Clear all
cache_clear("odds_nederland_japan")  # Clear specific match
```

## Next Steps (Phase 2 - Future)

- [ ] Integrate real APIs (The Odds API, API-Football)
- [ ] Add bonus tracking (tournament winner, top scorer)
- [ ] Auto-resolve knock-out teams from group results
- [ ] Pool leaderboard tracking
- [ ] Discord/Slack notifications for match insights
- [ ] Mobile-friendly responsive UI

## Troubleshooting

**"No module named streamlit"**
```bash
pip install -r requirements.txt
```

**"Cache permission error"**
```bash
mkdir -p cache && chmod 755 cache
```

**"App won't load"**
Check for Python syntax errors:
```bash
python -m py_compile app.py
```

## License

Personal use for VroenWK2026 family pool. Not for commercial purposes.

## Contact

Questions or improvements? Contact the pool organizer.

---

**Built with** Python, Streamlit, SciPy, Poisson distribution, EV optimization, and family pool love ❤️