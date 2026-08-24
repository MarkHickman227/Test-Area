from app.services.pricing import PricingInput, calculate_credit_cost


def test_formula_matches_spec():
    cost = calculate_credit_cost(
        PricingInput(base_model_cost=4, resolution="768x1152", image_count=2)
    )
    assert cost == round(4 * 1.25 * 2)


def test_square_one_image():
    assert (
        calculate_credit_cost(
            PricingInput(base_model_cost=4, resolution="768x768", image_count=1)
        )
        == 4
    )
