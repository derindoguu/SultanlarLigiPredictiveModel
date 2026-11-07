# Sultanlar Ligi predictive model

This project predicts matches in the Sultanlar Ligi, Turkey's top women's volleyball league. It rates every team with an Elo model, then simulates a match to estimate who wins and the chance of each final score.

New results come from the [Turkish Volleyball Federation (TVF) fixture](https://tvf.org.tr/lig/sultanlar-ligi?sekme=fikstur). A GitHub Action is set up to add them every Monday.

- [Quick start](#quick-start)
- [How the model works](#how-the-model-works)
- [How to use it](#how-to-use-it)
- [How accurate it is](#how-accurate-it-is)
- [Limitations](#limitations)
- [Project files](#project-files)
- [Maintenance](#maintenance)

## Quick start

**To see predictions:** open `dashboard.html` in a browser, then pick a home and an away team. Keep `dashboard_data.js` in the same folder, because the page reads its data from there.

**To work with the code:** you need Python 3.9.

```powershell
pip install -r requirements.txt
pytest                              # check that everything works
python update_ratings.py            # fetch new results and update the outputs
python update_ratings.py --offline  # rebuild the outputs from the saved data
```

## How the model works

A prediction takes four steps. The example uses VakıfBank at home to Fenerbahçe, with ratings from 5 November 2026.

### 1. Rate every team

Each team has an Elo rating, where a higher number means a stronger team. VakıfBank's rating is 1945 and Fenerbahçe's is 1894.

| Team | Starting rating |
|---|---|
| Teams in the first season of the data (2021-22) | 1500 |
| Teams that appear later | 1300 |

Ratings carry over from one season to the next without being reset.

### 2. Work out the expected score

The ratings give an expected score between 0 and 1, after adding 25 rating points to the home team:

```text
expected score = 1 / (1 + 10 ^ ((away rating - (home rating + 25)) / 400))
```

VakıfBank's expected score is **0.607**. This is not a win probability, because the model scores matches on a scale that rewards how convincingly a team wins:

| Final score | 3-0 | 3-1 | 3-2 | 2-3 | 1-3 | 0-3 |
|---|---|---|---|---|---|---|
| Home team's score | 1.0 | 0.8 | 0.6 | 0.4 | 0.2 | 0.0 |

### 3. Convert it to a chance of winning a set

The model finds the chance of winning a single set that would produce that expected score over a best-of-five match. For VakıfBank, that's **58.5%** per set.

### 4. Simulate the match

The match is played 100,000 times, set by set, until a team reaches 3 sets. Counting the results gives the win chance and the chance of each final score:

| 3-0 | 3-1 | 3-2 | 2-3 | 1-3 | 0-3 | Home win |
|---|---|---|---|---|---|---|
| 20.0% | 24.9% | 20.7% | 14.7% | 12.6% | 7.2% | **65.6%** |

The win chance (65.6%) is higher than the set chance (58.5%), because a small edge in each set adds up over a match.

These are the exact probabilities. Simulated results differ slightly each time, by a few tenths of a percentage point, unless you fix the `seed`.

### After each match

Both teams' ratings move by the same amount in opposite directions:

```text
change = 110 x (actual score - expected score)
```

| If VakıfBank wins or loses | Actual score | VakıfBank's rating |
|---|---|---|
| Wins 3-0 | 1.0 | +43 |
| Wins 3-1 | 0.8 | +21 |
| Loses 1-3 | 0.2 | -45 |

A team gains more for beating expectations, and ratings can move quickly: the factor of 110 was chosen by testing on past seasons.

## How to use it

### The dashboard

Pick the two teams, and tick **neutral venue** if neither has home advantage. The page is in Turkish by default, and you can switch to English at the top.

| On the dashboard | What it means |
|---|---|
| Name in capitals | The team's full current name, with its sponsor, as written in the TVF fixture |
| Large percentages | Each team's chance of winning the match, in whole numbers because the model isn't precise enough for decimals |
| *Team* wins a set | The home team's chance in any single set |
| Match goes to a tie-break set | The chance of a 3-2 or 2-3 finish |
| Expected league points | The average points each team takes from the match: 3 for a 3-0 or 3-1 win, 2 for a 3-2 win, 1 for a 2-3 loss |
| Chance of each final score | A chart of all six results, with the home team's sets first and the league points the winner earns |
| Most likely | The single most likely final score |
| Last 5 | Each team's latest results, oldest first, with wins in green and losses in red. Hover over or tap a square to see the opponent and score |
| Head to head | Wins between the two teams since the data begins |
| Yellow warning | The model's win chance is above 90% or below 10%, where it has been overconfident |

### From Python

Team ids are in `teams.csv`.

```python
from sultanlar.data import load_matches
from sultanlar.elo import run_elo
from sultanlar.simulation import simulate_match

games, ratings = run_elo(load_matches())

result = simulate_match("VAK", "FEN", ratings, seed=42)
print(result["home_win"])       # chance the home team wins
print(result["p_set"])          # chance the home team wins a set
print(result["scorelines"])     # chance of each final score

neutral = simulate_match("VAK", "FEN", ratings, H=0, seed=42)
```

The current ratings are also saved in `ratings.csv`.

### The notebook

Use `EloModelV2.ipynb` to look at past ratings, check accuracy and calibration, or test other settings. To try a setting without changing anything, pass it to the model, for example `run_elo(df, K=80)`. To adopt it, change `config.json`, then run `python update_ratings.py --offline`.

### Reading the predictions

- **Treat percentages as estimates.** A difference of a few points between two matches means little.
- **Be sceptical of extreme numbers.** A chance shown as >99% doesn't mean an upset is nearly impossible. See [how accurate it is](#how-accurate-it-is).
- **Check how recent the ratings are.** The dashboard shows the date of the last match included.
- **Use your own knowledge as well.** The model doesn't know about injuries, transfers or rested players.
- **Don't rely on it for betting.** It hasn't been compared with betting odds.

## How accurate it is

These figures use each match's ratings from before it was played. A log loss of 0.693 is what a coin flip would score, and lower is better.

| Season | Matches | Favourite won | Log loss |
|---|---|---|---|
| 2022-23 | 199 | 83.4% | 0.380 |
| 2023-24 | 202 | 80.2% | 0.420 |
| 2024-25 | 201 | 77.6% | 0.460 |
| 2025-26 | 199 | 80.9% | 0.410 |
| 2026-27 (to 5 Nov 2026) | 48 | 75.0% | 0.475 |
| **All** | **849** | **80.2%** | **0.421** |

2021-22 is left out because every team was still starting from the same rating. `K` and `S` were tuned on 2022-23 to 2024-25, so those seasons are slightly flattering. 2025-26 and 2026-27 are the fairer test.

Always picking the home team would be right 52.7% of the time.

The simulated win chances are too confident in lopsided matches:

| Model's home win chance | Matches | Average prediction | Home team actually won |
|---|---|---|---|
| Above 90% | 220 | 97.2% | 95.5% |
| Below 10% | 189 | 2.8% | 8.5% |

The dashboard updates its overall accuracy and these two groups on every run. This table is a snapshot from 5 November 2026.

## Limitations

- **Only results are used.** The model ignores squads, transfers, injuries, coaches and rest.
- **Ratings lag behind real changes.** A team that rebuilt over the summer starts the season on its old rating.
- **New teams are uncertain.** They start at 1300 whatever their real strength, and need several matches to settle.
- **Sets are treated as independent.** Every set has the same chance, so momentum and the shorter tie-break set aren't modelled. This is one likely reason for the overconfidence above.
- **Home advantage is the same for every team and venue.**
- **Forfeits are left out of the ratings.**
- **Playoff data isn't confirmed.** Only regular-season matches have been seen on the TVF page so far.

## Project files

| File | What it is | Edit it? |
|---|---|---|
| `config.json` | Model settings, scoring rules, simulation settings, TVF address and file paths | Yes |
| `teams.csv` | Each team's id, display name and the word that identifies it in TVF names | Yes |
| `sultanlar_ligi_2021-2026.xlsx` | Match history to 2025-26, from Wikipedia and Flashscore | Rarely |
| `active_season_matches.csv` | Matches from TVF, added by the update | No |
| `ratings.csv`, `dashboard_data.js` | Generated by the update | No |
| `dashboard.html` | Dashboard layout and text in both languages | For design and wording |
| `EloModelV2.ipynb` | Analysis, calibration and tuning | Yes |
| `update_ratings.py` | Runs the update from start to finish | Rarely |
| `.github/workflows/update-ratings.yml` | The weekly GitHub Action | Rarely |

| Code in `sultanlar/` | What it does |
|---|---|
| `tvf.py` | Reads and checks the TVF fixture |
| `data.py` | Loads, merges, checks and saves match data |
| `elo.py` | The Elo model |
| `simulation.py` | Set probabilities and the Monte Carlo simulation |
| `evaluation.py` | The model's track record |
| `outputs.py` | Builds the ratings table and dashboard data |

### Settings

The `model` section of `config.json` controls the model, and a change there reaches the code, notebook and dashboard:

| Setting | Value | Meaning |
|---|---|---|
| `K` | 110 | How far ratings move after a match |
| `H` | 25 | Home advantage, in rating points |
| `S` | 400 | Scale: a larger value turns the same rating gap into a smaller edge |
| `start` | 1500 | Rating of teams in the first season |
| `promoted` | -200 | Adjustment for teams that appear later |
| `revert` | 0.0 | Share of each rating pulled back to the league average between seasons |

Run `python update_ratings.py --offline` after changing a setting.

## Maintenance

### Every October, before the season

1. In GitHub, check that the workflow is still enabled under **Actions**. GitHub turns scheduled workflows off after 60 days without repository activity, which can happen over the summer.
2. Compare the teams on the TVF page with `teams.csv`, and add new teams.
3. Run the workflow by hand to confirm it works.

### When the update fails

GitHub emails you, and nothing is saved. Open the failed run and read the last error:

| Error | Meaning | Fix |
|---|---|---|
| `Cannot match TVF team` | A new team, or a name that no longer contains its keyword | Add or edit the row in `teams.csv` |
| `No fixture data` or `missing fields` | TVF changed its website | Update `sultanlar/tvf.py` |
| `do not give`, `Impossible score` | A wrong result on TVF | Wait for TVF to correct it |
| `Same regular-season match twice` | TVF renumbered its matches | Remove the old rows from `active_season_matches.csv` |
| HTTP or timeout error | TVF is down or blocking the request | Run again later, or run it on your own computer |

### Each spring

Check that playoff matches appear in `active_season_matches.csv`.

### Once a year, after the season

- Rerun the notebook. If tuning finds better settings, change `model` in `config.json`. The test `test_ratings_on_the_workbook_are_unchanged` will then fail on purpose, so update its expected values.
- Update the versions in `requirements.txt` and `.python-version` together, then run `pytest`.
- Finished seasons can stay in `active_season_matches.csv`. If you move one into the workbook, do it in Excel and delete its rows from the CSV, or the update will stop on duplicate match ids.
