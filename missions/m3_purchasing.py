"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def carbon_aware_schedule(jobs: list[dict], catalog: dict,
                          current_region: str = "us-east-1") -> dict:
    """So sánh chi phí điện và carbon cho các job có thể gián đoạn."""
    job_rows = []
    total_kwh = 0.0
    for job in jobs:
        if not bool(int(num(job["interruptible"]))):
            continue
        gpu_type = job["gpu_type"]
        gpu_hours = (
            num(job["hours_per_day"])
            * num(job["days"])
            * int(num(job["num_gpus"]))
        )
        energy_kwh = gpu_hours * num(catalog[gpu_type]["watts"]) / 1000.0
        total_kwh += energy_kwh
        job_rows.append({
            "job_id": job["job_id"],
            "gpu_type": gpu_type,
            "energy_kwh": round(energy_kwh, 2),
        })

    regions = []
    for region, carbon_intensity in sustainability.REGION_CARBON.items():
        electricity_cost = total_kwh * sustainability.REGION_PRICE_KWH[region]
        carbon_kg = total_kwh * carbon_intensity / 1000.0
        regions.append({
            "region": region,
            "price_kwh": sustainability.REGION_PRICE_KWH[region],
            "carbon_g_kwh": carbon_intensity,
            "electricity_cost_usd": round(electricity_cost, 2),
            "carbon_kg": round(carbon_kg, 2),
        })

    cheapest = min(regions, key=lambda row: row["electricity_cost_usd"])
    cleanest = min(regions, key=lambda row: row["carbon_kg"])
    min_price = min(row["price_kwh"] for row in regions)
    min_carbon = min(row["carbon_g_kwh"] for row in regions)
    balanced = min(
        regions,
        key=lambda row: (
            row["price_kwh"] / min_price
            + row["carbon_g_kwh"] / min_carbon
        ) / 2.0,
    )
    current = next(row for row in regions if row["region"] == current_region)
    carbon_saved = current["carbon_kg"] - cleanest["carbon_kg"]

    for job_row in job_rows:
        energy_kwh = job_row["energy_kwh"]
        job_row["current_carbon_kg"] = round(
            energy_kwh * sustainability.REGION_CARBON[current_region] / 1000.0, 2
        )
        job_row["clean_carbon_kg"] = round(
            energy_kwh * sustainability.REGION_CARBON[cleanest["region"]] / 1000.0, 2
        )

    return {
        "current_region": current_region,
        "total_energy_kwh": round(total_kwh, 2),
        "regions": regions,
        "jobs": job_rows,
        "cheapest_region": cheapest["region"],
        "cleanest_region": cleanest["region"],
        "balanced_region": balanced["region"],
        "carbon_saved_kg": round(carbon_saved, 2),
        "carbon_reduction_pct": round(carbon_saved / current["carbon_kg"] * 100, 1)
        if current["carbon_kg"] else 0.0,
        "electricity_savings_usd": round(
            current["electricity_cost_usd"] - cleanest["electricity_cost_usd"], 2
        ),
    }


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0
    carbon_schedule = carbon_aware_schedule(jobs, cat)

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

        print("\nCarbon-aware scheduling (interruptible jobs):")
        print(f"{'region':18}{'$/kWh':>8}{'gCO2/kWh':>12}{'electricity':>14}{'carbon kg':>12}")
        for row in carbon_schedule["regions"]:
            print(
                f"{row['region']:18}{row['price_kwh']:>8.3f}"
                f"{row['carbon_g_kwh']:>12.0f}${row['electricity_cost_usd']:>13,.2f}"
                f"{row['carbon_kg']:>12,.2f}"
            )
        print(
            f"  cheapest={carbon_schedule['cheapest_region']}, "
            f"cleanest={carbon_schedule['cleanest_region']}, "
            f"balanced={carbon_schedule['balanced_region']}"
        )
        print(
            f"  move from {carbon_schedule['current_region']} to "
            f"{carbon_schedule['cleanest_region']}: save "
            f"{carbon_schedule['carbon_saved_kg']:,.2f} kgCO2e "
            f"({carbon_schedule['carbon_reduction_pct']:.1f}%)"
        )

    return {
        "recommendations": recs,
        "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly),
        "savings_pct": round(savings_pct, 1),
        "carbon_schedule": carbon_schedule,
    }


if __name__ == "__main__":
    run()
