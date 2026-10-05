import math

from app.montecarlo.mitigation import apply_mitigation
from app.montecarlo.simulate import MonteCarloParams, default_sigma, run_simulation


def test_same_seed_is_reproducible():
    params = MonteCarloParams(p_annual=0.3, median_severity=1_000_000, sigma=0.6, n_sims=20_000)
    losses_a, result_a = run_simulation(params)
    losses_b, result_b = run_simulation(params)

    assert (losses_a == losses_b).all()
    assert result_a.mean == result_b.mean
    assert result_a.var95 == result_b.var95


def test_different_seed_gives_different_result():
    base = MonteCarloParams(p_annual=0.3, median_severity=1_000_000, sigma=0.6, n_sims=20_000)
    other = MonteCarloParams(
        p_annual=0.3, median_severity=1_000_000, sigma=0.6, n_sims=20_000, seed=999
    )
    _, result_a = run_simulation(base)
    _, result_b = run_simulation(other)
    assert result_a.mean != result_b.mean


def test_simulated_mean_matches_analytic_compound_poisson_mean():
    # For a compound Poisson process, E[annual loss] = lambda * E[severity]
    # = lambda * median * exp(sigma^2/2) (Wald's identity + lognormal mean).
    p_annual, median_severity, sigma = 0.25, 2_000_000.0, 0.7
    params = MonteCarloParams(
        p_annual=p_annual, median_severity=median_severity, sigma=sigma, n_sims=200_000
    )

    _, result = run_simulation(params)

    analytic_mean = params.lam * median_severity * math.exp(sigma**2 / 2)
    relative_error = abs(result.mean - analytic_mean) / analytic_mean
    assert relative_error < 0.05, f"{result.mean=} vs {analytic_mean=}"


def test_zero_probability_gives_zero_loss():
    params = MonteCarloParams(p_annual=0.0, median_severity=1_000_000, sigma=0.5, n_sims=1_000)
    _, result = run_simulation(params)
    assert result.mean == 0.0
    assert result.var95 == 0.0


def test_var_and_cvar_ordering():
    params = MonteCarloParams(p_annual=0.4, median_severity=500_000, sigma=0.8, n_sims=50_000)
    _, result = run_simulation(params)

    assert result.var99 >= result.var95
    assert result.cvar95 >= result.var95
    assert result.cvar99 >= result.var99


def test_default_sigma_increases_with_wider_tail():
    narrow = default_sigma(median_severity=1_000_000, q95=1_500_000)
    wide = default_sigma(median_severity=1_000_000, q95=5_000_000)
    assert wide > narrow


def test_mitigation_reduces_both_frequency_and_severity():
    base = MonteCarloParams(p_annual=0.4, median_severity=1_000_000, sigma=0.6, n_sims=1_000)
    mitigated = apply_mitigation(base, effectiveness_frequency=0.3, effectiveness_severity=0.2)

    assert mitigated.p_annual == base.p_annual * 0.7
    assert mitigated.median_severity == base.median_severity * 0.8
    assert mitigated.lam < base.lam


def test_mitigated_simulation_has_lower_expected_loss():
    base = MonteCarloParams(p_annual=0.4, median_severity=1_000_000, sigma=0.6, n_sims=100_000)
    mitigated = apply_mitigation(base, effectiveness_frequency=0.3, effectiveness_severity=0.3)

    _, base_result = run_simulation(base)
    _, mitigated_result = run_simulation(mitigated)

    assert mitigated_result.mean < base_result.mean
    assert mitigated_result.var95 < base_result.var95
