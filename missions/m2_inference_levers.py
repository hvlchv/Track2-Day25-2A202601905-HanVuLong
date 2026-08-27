"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
CACHE_WRITE_PREMIUM = 1.25
REASONING_TRAFFIC_CAP = 0.05


def _cache_policy(rows: list[dict]) -> dict:
    """Ước lượng reuse theo project+tier và chỉ bật cache khi vượt hòa vốn."""
    reads_by_group = defaultdict(int)
    for r in rows:
        if int(num(r["cached_input_tokens"])) <= 0:
            continue
        project = r.get("project") or r.get("team") or "(unknown)"
        reads_by_group[(r["route_tier"], project)] += 1

    policy = {}
    for tier, (price_in, _) in MODEL_PRICES.items():
        observed = [count for (group_tier, _), count in reads_by_group.items()
                    if group_tier == tier]
        avg_reads = sum(observed) / len(observed) if observed else 0.0
        write_cost = price_in * CACHE_WRITE_PREMIUM
        break_even = pricing.cache_break_even_reads(
            write_cost_per_m=write_cost,
            price_in_per_m=price_in,
            read_discount=0.10,
        )
        policy[tier] = {
            "avg_reads": round(avg_reads, 1),
            "break_even_reads": round(break_even, 2),
            "enabled": pricing.cache_is_worth_it(
                avg_cache_reads=avg_reads,
                write_cost_per_m=write_cost,
                read_discount=0.10,
                price_in_per_m=price_in,
            ),
        }
    return policy


def _optimized_request_cost(
    row: dict,
    cache_policy: dict,
    force_tier: str | None = None,
) -> float:
    inp = int(num(row["input_tokens"]))
    out = int(num(row["output_tokens"]))
    tier = force_tier or row["route_tier"]
    cached = int(num(row["cached_input_tokens"])) if cache_policy[tier]["enabled"] else 0
    is_batch = bool(int(num(row["is_batch"])))
    price_in, price_out = MODEL_PRICES[tier]
    return pricing.request_cost(
        inp,
        out,
        price_in,
        price_out,
        cached_in=cached,
        batch=is_batch,
    )


def _reasoning_budget(rows: list[dict], cache_policy: dict) -> dict:
    """Đo chi phí reasoning và mô phỏng giới hạn theo policy traffic."""
    reasoning_indices = [
        i for i, row in enumerate(rows) if bool(int(num(row["is_reasoning"])))
    ]
    target_count = int(len(rows) * REASONING_TRAFFIC_CAP)
    # Không có complexity score; tổng token là proxy minh bạch cho độ phức tạp.
    retained = set(sorted(
        reasoning_indices,
        key=lambda i: int(num(rows[i]["input_tokens"])) + int(num(rows[i]["output_tokens"])),
        reverse=True,
    )[:target_count])

    reasoning_cost = normal_cost = current_wh = capped_wh = capped_cost = 0.0
    reasoning_wh = normal_wh = 0.0
    for i, row in enumerate(rows):
        tokens = int(num(row["input_tokens"])) + int(num(row["output_tokens"]))
        is_reasoning = i in reasoning_indices
        current_cost = _optimized_request_cost(row, cache_policy)
        current_energy = sustainability.wh_per_query(tokens, is_reasoning=is_reasoning)
        current_wh += current_energy
        if is_reasoning:
            reasoning_cost += current_cost
            reasoning_wh += current_energy
        else:
            normal_cost += current_cost
            normal_wh += current_energy

        if is_reasoning and i not in retained:
            capped_cost += _optimized_request_cost(row, cache_policy, force_tier="small")
            capped_wh += sustainability.wh_per_query(tokens, is_reasoning=False)
        else:
            capped_cost += current_cost
            capped_wh += current_energy

    total_cost = reasoning_cost + normal_cost
    total_count = len(rows)
    return {
        "reasoning_requests": len(reasoning_indices),
        "traffic_pct": round(len(reasoning_indices) / total_count * 100, 1) if total_count else 0.0,
        "cost_daily": round(reasoning_cost, 2),
        "cost_share_pct": round(reasoning_cost / total_cost * 100, 1) if total_cost else 0.0,
        "energy_wh_daily": round(reasoning_wh, 2),
        "energy_share_pct": round(reasoning_wh / current_wh * 100, 1) if current_wh else 0.0,
        "normal_cost_daily": round(normal_cost, 2),
        "normal_energy_wh_daily": round(normal_wh, 2),
        "cap_pct": REASONING_TRAFFIC_CAP * 100,
        "retained_requests": len(retained),
        "dollar_savings_daily": round(max(0.0, total_cost - capped_cost), 2),
        "energy_savings_wh_daily": round(max(0.0, current_wh - capped_wh), 2),
    }


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    cache_policy = _cache_policy(rows)
    base_cost = opt_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        total_tokens += inp + out
        # BASELINE: mọi request dùng model lớn, không cache, không batch.
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade + cache có kiểm tra hòa vốn + batch API.
        opt_cost += _optimized_request_cost(r, cache_policy)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    reasoning = _reasoning_budget(rows, cache_policy)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("\nCache economics:")
        for tier, values in cache_policy.items():
            print(
                f"  {tier:5} avg_reads={values['avg_reads']:>6.1f}, "
                f"break-even>{values['break_even_reads']:.2f}, enabled={values['enabled']}"
            )
        print("\nReasoning budget:")
        print(
            f"  {reasoning['traffic_pct']:.1f}% traffic -> "
            f"{reasoning['cost_share_pct']:.1f}% cost, "
            f"{reasoning['energy_share_pct']:.1f}% energy"
        )
        print(
            f"  cap at {reasoning['cap_pct']:.0f}% saves "
            f"${reasoning['dollar_savings_daily']:.2f}/day and "
            f"{reasoning['energy_savings_wh_daily']:.1f} Wh/day"
        )

    return {
        "baseline_daily": round(base_cost, 2),
        "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3),
        "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1),
        "total_tokens": total_tokens,
        "cache_economics": cache_policy,
        "reasoning_budget": reasoning,
    }


if __name__ == "__main__":
    run()
