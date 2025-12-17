import numpy as np
from numba import njit, prange

PNL_TOLERANCE = 0.9


@njit(parallel=True)
def monte_carlo(closed_positions: np.ndarray, num_runs: int) -> float:
    """
    Monte Carlo test for whether a trader's realized PnL can be explained
    by chance given the implied probabilities of each position.
    
    Accelerated using Numba

    Parameters
    ----------
    closed_positions : np.ndarray
        Array of shape (N, 3):
            [0] position size
            [1] realized PnL
            [2] probability of a winning outcome

    num_runs : int
        Number of Monte Carlo simulations to run.

    Returns
    -------
    float
        Fraction of simulations where simulated PnL >= realized PnL.
    """

    total = 0
    overall_pnl = 0.0

    # Compute realized PnL after filtering unresolved outcomes
    for i in range(len(closed_positions)):
        size = closed_positions[i, 0]
        realized = closed_positions[i, 1]
        prob = closed_positions[i, 2]

        if realized > 0:
            if realized < PNL_TOLERANCE * size * (1.0 - prob):
                continue
            overall_pnl += size * (1.0 - prob)
        else:
            if realized > -PNL_TOLERANCE * size * prob:
                continue
            overall_pnl -= size * prob

    # Monte Carlo simulation
    for _ in prange(num_runs):
        local = 0.0

        for i in range(len(closed_positions)):
            size = closed_positions[i, 0]
            realized = closed_positions[i, 1]
            prob = closed_positions[i, 2]

            # Skip  unresolved outcomes with expected payoff
            if realized > 0 and realized < PNL_TOLERANCE * size * (1.0 - prob):
                continue
            if realized <= 0 and realized > -PNL_TOLERANCE * size * prob:
                continue

            # Simulate win / loss
            if np.random.random() < prob:
                local += size * (1.0 - prob)
            else:
                local -= size * prob

        if local >= overall_pnl:
            total += 1

    return total / num_runs
