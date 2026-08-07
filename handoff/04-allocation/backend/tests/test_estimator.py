"""Layer 1 個別需求 + Layer 2 自由配 的測試。"""
from allocation.estimator import estimate, free_allocate, individual_needs
from allocation.models import ClientInputs, IndependentNeeds

DEMO = ClientInputs(
    age=42, retire_age=65, monthly_investable=30000,
    dependents=1, risk_tolerance="mid",
    has_medical_coverage=True, has_life_coverage=True,
)


def test_individual_needs_are_independent_not_normalized():
    needs = individual_needs(DEMO)
    # 各自獨立純算,刻意不加總 100
    assert needs.a == 53
    assert needs.b == 21
    assert round(needs.c, 1) == 8.8
    assert abs(needs.total - 100) > 1  # 合計 82.8,不是 100


def test_free_allocate_sums_to_100():
    needs = individual_needs(DEMO)
    alloc = free_allocate(needs)
    assert alloc.a + alloc.b + alloc.c == 100


def test_demo_free_allocation_values():
    needs, alloc = estimate(DEMO)
    assert (alloc.a, alloc.b, alloc.c) == (64, 25, 11)


def test_free_allocate_degenerate_zero_needs():
    alloc = free_allocate(IndependentNeeds(a=0, b=0, c=0))
    assert alloc.a + alloc.b + alloc.c == 100


def test_longer_horizon_raises_financial_need():
    young = ClientInputs(age=30, retire_age=65)
    older = ClientInputs(age=55, retire_age=65)
    assert individual_needs(young).a > individual_needs(older).a


def test_no_medical_coverage_raises_c_need():
    with_cov = ClientInputs(age=50, retire_age=65, has_medical_coverage=True)
    without = ClientInputs(age=50, retire_age=65, has_medical_coverage=False)
    assert individual_needs(without).c > individual_needs(with_cov).c


def test_estimate_always_sums_100_across_many_clients():
    for age in range(25, 70, 3):
        for dep in range(0, 4):
            _, alloc = estimate(ClientInputs(age=age, retire_age=65, dependents=dep))
            assert alloc.a + alloc.b + alloc.c == 100
