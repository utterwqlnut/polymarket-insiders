import random
from typing import List, Tuple
from numba import prange, njit
import numpy as np

@njit(parallel=True)
def monte_carlo(closed_positions: np.ndarray, num_runs: int):
    total = 0
    overalPnl = 0.0
    
    for i in range(len(closed_positions)):
        if closed_positions[i,1] > 0:
            if closed_positions[i,1] < 0.9*closed_positions[i,0]*(1-closed_positions[i,2]):
                continue
            overalPnl += closed_positions[i,0]*(1-closed_positions[i,2])
        else:
            if closed_positions[i,1] > 0.9*-closed_positions[i,0]*closed_positions[i,2]:
                continue
            overalPnl -= closed_positions[i,0]*closed_positions[i,2]

    for _ in prange(num_runs):
        local = 0.0
        for i in range(len(closed_positions)):
            if closed_positions[i,1] < 0.9*closed_positions[i,0]*(1-closed_positions[i,2]) and closed_positions[i,1] > 0:
                continue
            if closed_positions[i,1] > 0.9*-closed_positions[i,0]*closed_positions[i,2] and closed_positions[i,1] <= 0:
                continue
            if np.random.random() < closed_positions[i,2]:
                local += closed_positions[i,0]*(1-closed_positions[i,2])
            else:
                local -= closed_positions[i,0]*closed_positions[i,2]

        if local >= overalPnl:
            total += 1

    return total / num_runs