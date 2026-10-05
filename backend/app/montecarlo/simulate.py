"""Frequency-severity Monte Carlo for a single Treat-zone risk.

Frequency: N ~ Poisson(lambda), lambda = -ln(1 - P) (continuous-time
    annualized rate implied by an annual occurrence probability P).
Severity: lognormal, median = Impact$ (the point estimate from
    scoring/impact.py), sigma = ln(q95/median) / 1.645.

q95 (the severity distribution's 95th percentile) isn't an
independently measured figure here - there's no tail-loss dataset
behind this build - so it's q95 = median * Q95_MULTIPLIER, a config
assumption (DEFAULT_Q95_MULTIPLIER), unless the caller overrides sigma
directly. This is the documented fallback the spec explicitly allows
for ("fallback sigma default from config").

Annual loss for one simulated year = sum of N draws from the severity
distribution. Vectorized with numpy.random.default_rng(seed).
"""

import math
from dataclasses import dataclass, field

import numpy as np

DEFAULT_N_SIMS = 100_000
DEFAULT_HORIZON_YEARS = 1
DEFAULT_Q95_MULTIPLIER = 3.0  # assumption: tail severity = 3x the median case
_Z_95 = 1.645


@dataclass
class MonteCarloParams:
    p_annual: float  # annual occurrence probability -> lambda = -ln(1-p)
    median_severity: float
    sigma: float
    horizon_years: int = DEFAULT_HORIZON_YEARS
    n_sims: int = DEFAULT_N_SIMS
    seed: int = 42

    @property
    def lam(self) -> float:
        p = min(max(self.p_annual, 0.0), 0.999999)
        return -math.log(1 - p)


@dataclass
class MonteCarloResult:
    mean: float
    median: float
    var95: float
    var99: float
    cvar95: float
    cvar99: float
    hist_bins: dict = field(default_factory=dict)  # {"edges": [...], "counts": [...]}
    exceedance: dict = field(default_factory=dict)  # {"loss": [...], "prob": [...]}


def default_sigma(median_severity: float, q95: float | None = None) -> float:
    if median_severity <= 0:
        return 0.5
    effective_q95 = q95 if q95 is not None else median_severity * DEFAULT_Q95_MULTIPLIER
    ratio = max(effective_q95 / median_severity, 1.0 + 1e-9)
    return math.log(ratio) / _Z_95


def run_simulation(params: MonteCarloParams) -> tuple[np.ndarray, MonteCarloResult]:
    rng = np.random.default_rng(params.seed)
    n_sims = params.n_sims

    n_events = rng.poisson(lam=params.lam * params.horizon_years, size=n_sims)
    max_events = int(n_events.max())

    if max_events == 0 or params.median_severity <= 0:
        losses = np.zeros(n_sims)
    else:
        mu = math.log(params.median_severity)
        severities = rng.lognormal(mean=mu, sigma=params.sigma, size=(n_sims, max_events))
        event_mask = np.arange(max_events)[None, :] < n_events[:, None]
        losses = (severities * event_mask).sum(axis=1)

    var95 = float(np.percentile(losses, 95))
    var99 = float(np.percentile(losses, 99))
    tail95 = losses[losses >= var95]
    tail99 = losses[losses >= var99]

    counts, edges = np.histogram(losses, bins=50)

    sorted_losses = np.sort(losses)[::-1]
    sample_points = np.linspace(0, n_sims - 1, 100, dtype=int)
    exceedance_loss = sorted_losses[sample_points]
    exceedance_prob = (sample_points + 1) / n_sims

    result = MonteCarloResult(
        mean=float(losses.mean()),
        median=float(np.median(losses)),
        var95=var95,
        var99=var99,
        cvar95=float(tail95.mean()) if len(tail95) else var95,
        cvar99=float(tail99.mean()) if len(tail99) else var99,
        hist_bins={"edges": edges.tolist(), "counts": counts.tolist()},
        exceedance={"loss": exceedance_loss.tolist(), "prob": exceedance_prob.tolist()},
    )
    return losses, result


def prob_loss_exceeds(losses: np.ndarray, threshold: float) -> float:
    return float((losses > threshold).mean())
