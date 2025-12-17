# Polymarket Insiders

This is a real-time pipeline for flagging Polymarket traders whose on-chain performance is statistically hard to explain.

It watches trades as they happen, identifies large positions, pulls full realized trade histories for those users, and estimates the likelihood that their results occurred by chance.

That likelihood is then converted into an insider score. Users with the most unlikely outcomes float to the top of a rolling leaderboard.


## Methods

The system is split into a simple producer / consumer pipeline.

1. The producer continuously scans on-chain Polymarket trades and flags unusually large trades.
2. The consumer takes each flagged trade and pulls the user’s full **realized trade history**.
3. For each realized trade, price is treated as an implied probability.
4. Monte Carlo simulations are run to estimate the probability of achieving a simulated PnL greater than or equal to the user’s actual PnL, using only fully realized trades.
5. This probability is converted into an insider score.
6. `(user, score)` pairs are written to a Redis sorted set, which is trimmed to keep the top 1000 users.
7. A FastAPI service exposes the leaderboard via an HTTP endpoint.

## Stack

- Python (async)
- FastAPI
- Redis
- Numba (JIT speedups for Monte Carlo simulation)
- Docker

## Running It

```bash
git clone https://github.com/utterwqlnut/polymarket-insiders.git
cd polymarket-insiders
pip install -r requirements.txt
export REDIS_URL="redis://localhost:6379"
python server/main.py
```
