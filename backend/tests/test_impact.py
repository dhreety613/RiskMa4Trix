from app.scoring.impact import compute_impact


def test_interest_rate_driver_uses_total_debt_directly():
    result = compute_impact(
        category_slug="interest_rate",
        revenue=100_000,
        ebitda=20_000,
        total_debt=50_000,
        mcap=1_000_000,
        dd95_1y=0.1,
    )
    # 200bps (default) * 50,000 debt = 1,000
    assert result.impact_usd == 1000.0
    assert result.impact_pct_ebitda == 1000.0 / 20_000
    assert "total_debt" not in " ".join(result.fallbacks)


def test_interest_rate_driver_falls_back_without_debt():
    result = compute_impact(
        category_slug="interest_rate",
        revenue=100_000,
        ebitda=20_000,
        total_debt=None,
        mcap=1_000_000,
        dd95_1y=0.1,
    )
    assert any("total_debt unavailable" in f for f in result.fallbacks)
    assert result.impact_usd > 0


def test_revenue_share_driver_uses_dd95_as_shock():
    result = compute_impact(
        category_slug="competition_pricing",  # revenue_share_assumption: 0.15
        revenue=100_000,
        ebitda=20_000,
        total_debt=None,
        mcap=1_000_000,
        dd95_1y=0.2,
    )
    # exposure = 100,000 * 0.15 = 15,000; impact = 15,000 * 0.2 = 3,000
    assert result.impact_usd == 15_000 * 0.2
    assert result.fallbacks == []  # nothing missing for this driver


def test_falls_back_to_market_cap_when_ebitda_non_positive():
    result = compute_impact(
        category_slug="competition_pricing",
        revenue=100_000,
        ebitda=-5_000,
        total_debt=None,
        mcap=1_000_000,
        dd95_1y=0.2,
    )
    assert any("market cap" in f for f in result.fallbacks)
    assert result.impact_pct_ebitda == (15_000 * 0.2) / 1_000_000


def test_zero_impact_when_no_denominator_available():
    result = compute_impact(
        category_slug="competition_pricing",
        revenue=100_000,
        ebitda=None,
        total_debt=None,
        mcap=None,
        dd95_1y=0.2,
    )
    assert result.impact_pct_ebitda == 0.0
    assert any("neither EBITDA nor market cap" in f for f in result.fallbacks)


def test_impact_norm_is_monotonic_in_impact_pct():
    small = compute_impact("competition_pricing", 100_000, 20_000, None, None, 0.05)
    big = compute_impact("competition_pricing", 100_000, 20_000, None, None, 0.9)
    assert 0.0 <= small.impact_norm <= 1.0
    assert 0.0 <= big.impact_norm <= 1.0
    assert big.impact_norm > small.impact_norm
    assert big.impact_band >= small.impact_band


def test_unknown_category_uses_default_driver():
    result = compute_impact(
        category_slug="not_a_real_category",
        revenue=100_000,
        ebitda=20_000,
        total_debt=None,
        mcap=None,
        dd95_1y=0.1,
    )
    assert result.impact_usd > 0  # falls back to default revenue_share, doesn't crash
