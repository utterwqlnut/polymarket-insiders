import argparse

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suspicious_size", type=float, default=10000)
    parser.add_argument("--max_trades_per_call", type=int, default=100)
    parser.add_argument("--rate", type=int, default=5)
    parser.add_argument("--limit_history", type=int, default=100)
    parser.add_argument("--monte_carlo_runs", type=int, default=10000)

    args = parser.parse_args()

    return args