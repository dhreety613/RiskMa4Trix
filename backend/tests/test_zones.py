from app.scoring.zones import assign_zone


def test_low_probability_low_impact_is_tolerate():
    assert assign_zone(p_mean=0.05, impact_norm=0.1) == "tolerate"


def test_high_probability_low_impact_is_treat():
    assert assign_zone(p_mean=0.5, impact_norm=0.1) == "treat"


def test_low_probability_high_impact_is_transfer():
    assert assign_zone(p_mean=0.05, impact_norm=0.9) == "transfer"


def test_high_probability_high_impact_is_terminate():
    assert assign_zone(p_mean=0.5, impact_norm=0.9) == "terminate"


def test_exactly_at_threshold_counts_as_high():
    assert assign_zone(p_mean=0.20, impact_norm=0.50) == "terminate"


def test_custom_thresholds_are_respected():
    assert assign_zone(p_mean=0.3, impact_norm=0.3, p_threshold=0.5, impact_threshold=0.5) == (
        "tolerate"
    )
    assert assign_zone(p_mean=0.6, impact_norm=0.3, p_threshold=0.5, impact_threshold=0.5) == (
        "treat"
    )
