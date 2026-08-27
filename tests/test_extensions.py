import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from finops import pricing
from missions import m2_inference_levers, m3_purchasing, m5_report


def test_cache_break_even_policy():
    threshold = pricing.cache_break_even_reads(
        write_cost_per_m=1.25,
        price_in_per_m=1.0,
        read_discount=0.10,
    )
    assert abs(threshold - (1.25 / 0.9)) < 1e-9
    assert pricing.cache_is_worth_it(2.0, 1.25, 0.10, 1.0) is True
    assert pricing.cache_is_worth_it(1.0, 1.25, 0.10, 1.0) is False


def test_cache_economics_is_measured_from_dataset():
    result = m2_inference_levers.run(verbose=False)
    for values in result["cache_economics"].values():
        assert values["avg_reads"] > values["break_even_reads"]
        assert values["enabled"] is True


def test_reasoning_cap_saves_cost_and_energy():
    budget = m2_inference_levers.run(verbose=False)["reasoning_budget"]
    assert budget["traffic_pct"] > budget["cap_pct"]
    assert budget["cost_share_pct"] > budget["traffic_pct"]
    assert budget["energy_share_pct"] > budget["traffic_pct"]
    assert budget["dollar_savings_daily"] > 0
    assert budget["energy_savings_wh_daily"] > 0


def test_carbon_schedule_compares_all_regions():
    schedule = m3_purchasing.run(verbose=False)["carbon_schedule"]
    assert len(schedule["regions"]) == 5
    assert schedule["cleanest_region"] == "europe-north1"
    assert schedule["cheapest_region"] == "us-east-wa"
    assert schedule["carbon_saved_kg"] > 0
    assert schedule["carbon_reduction_pct"] > 80


def test_generated_report_is_vietnamese():
    m5_report.run(verbose=False)
    path = os.path.join(ROOT, "outputs", "report.md")
    content = open(path, encoding="utf-8").read()
    assert "Báo cáo Tối ưu Chi phí GPU" in content
    assert "Hiệu quả theo $/1M-token" in content
    assert "Ngân sách reasoning" in content
