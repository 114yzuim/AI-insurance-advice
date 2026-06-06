"""設定配求解器測試。"""
from allocation import default_constraints
from allocation.models import Allocation, Constraint
from allocation.solver import solve

# demo 客戶自由配 baseline(= test_estimator 的 A64/B25/C11)
BASE = Allocation(a=64, b=25, c=11)


def _c(cid, kind, bucket, value, active=True):
    return Constraint(id=cid, label=cid, kind=kind, bucket=bucket, value=value, active=active)


def test_demo_constraints_match_spec_example():
    cons = [
        _c("ins_floor", "floor", "B", 25),
        _c("med_must", "must_include", "C", 10),
        _c("fin_cap", "cap", "A", 60),
    ]
    r = solve(BASE, cons)
    assert r.feasible
    assert (r.allocation.a, r.allocation.b, r.allocation.c) == (60, 28, 12)
    assert r.allocation.total == 100
    assert "fin_cap" in r.binding  # 金融觸及上限
    assert "金融觸及上限 60%" in r.explanation


def test_result_always_sums_100_when_feasible():
    cons = [_c("fin_cap", "cap", "A", 50), _c("ins_floor", "floor", "B", 30)]
    r = solve(BASE, cons)
    assert r.feasible
    assert r.allocation.total == 100
    assert r.allocation.a <= 50
    assert r.allocation.b >= 30


def test_floor_pulls_bucket_up():
    base = Allocation(a=80, b=15, c=5)
    r = solve(base, [_c("med_must", "must_include", "C", 20)])
    assert r.feasible
    assert r.allocation.c >= 20
    assert r.allocation.total == 100


def test_cap_pushes_bucket_down():
    r = solve(BASE, [_c("fin_cap", "cap", "A", 40)])
    assert r.feasible
    assert r.allocation.a <= 40
    assert r.allocation.total == 100


def test_infeasible_floors_exceed_100():
    cons = [
        _c("a_floor", "floor", "A", 60),
        _c("b_floor", "floor", "B", 25),
        _c("c_floor", "must_include", "C", 20),
    ]
    r = solve(BASE, cons)
    assert r.feasible is False
    assert r.error and "超過 100%" in r.error


def test_infeasible_caps_below_100():
    cons = [
        _c("a_cap", "cap", "A", 30),
        _c("b_cap", "cap", "B", 30),
        _c("c_cap", "cap", "C", 30),
    ]
    r = solve(BASE, cons)
    assert r.feasible is False
    assert r.error and "不足 100%" in r.error


def test_inactive_constraint_ignored():
    r = solve(BASE, [_c("fin_cap", "cap", "A", 10, active=False)])
    assert r.feasible
    assert (r.allocation.a, r.allocation.b, r.allocation.c) == (64, 25, 11)


def test_liquidity_constraint_does_not_affect_buckets():
    cons = default_constraints()  # 含 active=False 的 liquidity
    r = solve(BASE, cons)
    assert r.feasible
    assert r.allocation.total == 100


def test_adjustments_reported():
    r = solve(BASE, [_c("fin_cap", "cap", "A", 60), _c("ins_floor", "floor", "B", 25), _c("med_must", "must_include", "C", 10)])
    by_bucket = {a.bucket: a for a in r.adjustments}
    assert by_bucket["A"].delta == -4  # 64 -> 60
    assert by_bucket["A"].baseline == 64
    assert by_bucket["A"].final == 60
