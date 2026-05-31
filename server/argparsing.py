import argparse

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suspicious_size", type=float, default=10000)
    parser.add_argument("--max_trades_per_call", type=int, default=100)
    parser.add_argument(
        "--rate",
        type=float,
        default=5.0,
        help="Seconds between trade API polls (decimal allowed, e.g. 0.5)",
    )
    parser.add_argument("--limit_history", type=int, default=10000)
    parser.add_argument("--monte_carlo_runs", type=int, default=10000)
    parser.add_argument(
        "--max_trading_age_days",
        type=int,
        default=120,
        help=(
            "Only score wallets whose first trade is at most this many days ago. "
            "Set to 0 to disable the age filter."
        ),
    )

    args = parser.parse_args()

    return args