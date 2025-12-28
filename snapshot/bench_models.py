# Minimal bench_models stub for local runs
from __future__ import annotations

def calculate_predicted_flight_constraint(horizontal_mps: float, vertical_mps: float, weight_n: float) -> float:
    """Return a simple predicted flight constraint (watts) approximation.

    This is a lightweight stub so the automation scripts can run without
    the full research model dependency. It approximates required power as
    proportional to horizontal and vertical speed scaled by weight.
    """
    try:
        h = float(abs(horizontal_mps))
        v = float(abs(vertical_mps))
        w = float(max(0.0, weight_n))
    except Exception:
        return 0.0
    # simple physics-inspired proxy: power ~ weight * speed * factor
    speed = (h ** 2 + v ** 2) ** 0.5
    factor = 0.1
    return float(w * speed * factor)
