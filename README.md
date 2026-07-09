# 🥊 NeuralFight

*A machine-learning model that predicts UFC fights — who wins, how they win, and where the betting line looks wrong.*

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white) ![React](https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)

NeuralFight trains on every completed UFC event scraped from [ufcstats.com](http://www.ufcstats.com): round-by-round significant strikes, takedowns, control time, submission attempts, plus fighter profiles (reach, height, DOB) and each bout's method and finish time. All of it lands in Postgres, and a nightly-ish scraper picks up new events incrementally so the model always trains on the full history.

Two LightGBM classifiers do the actual predicting. One is a binary winner model; the other is a multiclass method model that splits finishes into KO/TKO, submission, and decision. Both are fed the same ~27 features, and every feature is a *differential* between the two fighters rather than a raw stat, so the model reasons about the matchup instead of either corner in isolation. Among them:

- a from-scratch MMA Elo rating (K=200, bumped to 275 for a fighter's first three bouts, scaled by margin of victory so an early finish moves the needle more than a decision)
- career striking and grappling rates weighted by a one-year exponential time-decay, so recent form counts for more than fights from five years ago
- style-matchup interaction terms (striker-vs-grappler, wrestler-vs-striker, and so on) built from each fighter's own tendencies
- head-to-head history, shared-opponent results, win streaks, career trajectory, and an "output resilience" measure of how a fighter's striking holds up in losses
- context flags like title bouts and the smaller 25-foot APEX octagon

Training uses a strict chronological 70/15/15 split to avoid leakage, tunes hyperparameters with Optuna (50 trials), and calibrates probabilities with `CalibratedClassifierCV` — the objective is log loss, not raw accuracy, because a fight predictor is only useful if its 65% actually means 65%. A SHAP `TreeExplainer` runs on top of the winner model to turn each prediction into a written rationale ("the more accurate striker," "very difficult to take down," and so on).

## 💰 The betting side

Because a calibrated probability is only interesting next to a price, NeuralFight scrapes live MMA moneylines from BestFightOdds, averages them across sportsbooks, and converts them to implied probabilities. From there it surfaces two things: *upsets*, where the model favors the betting underdog, and *value bets*, where the model's edge over the book clears 3%. The performance page backtests the whole approach on the held-out test set, running a $10k bankroll simulation with edge-scaled stake sizing and reporting accuracy by confidence bucket, accuracy by finish method, and ROI against the Vegas baseline.

## 🛠️ Stack

FastAPI + SQLAlchemy backend (deployed on Railway), a React + TypeScript dashboard built with Vite and Tailwind (Vercel), and a standalone async httpx scraper package. The dashboard covers events, fighter pages, per-fight breakdowns, an upsets feed, a parlay builder, and bet history.

Predictions are for research and curiosity, not staking your rent on a Saturday-night prelim.
