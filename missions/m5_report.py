"""M5 — Báo cáo tổng hợp baseline-vs-optimized bằng tiếng Việt."""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from missions import (
    m1_efficiency_audit,
    m2_inference_levers,
    m3_purchasing,
    m4_allocation,
)

DAYS = 30
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def _extra_sections(r1: dict, r2: dict, r3: dict, r4: dict) -> list[dict]:
    lie_lines = []
    for item in r1["lies"]:
        lie_lines.append(
            f"- **{item['gpu_id']} ({item['gpu_type']})**: GPU-Util "
            f"{item['gpu_util_pct']:.1f}% nhưng MFU chỉ {item['mfu']:.1%}."
        )
    lie_lines += [
        "",
        "GPU-Util của `nvidia-smi` đo tỷ lệ thời gian clock GPU có hoạt động, "
        "không đo lượng FLOPs hữu ích. Memory stall, chờ I/O hoặc kernel nhỏ vẫn "
        "có thể làm GPU báo bận gần 100% trong khi chỉ khai thác một phần năng lực tính toán.",
        "",
        f"Chi phí idle đo được là **${r1['idle_waste_daily']:,.2f}/ngày**, tương đương "
        f"**${r1['idle_waste_daily'] * DAYS:,.0f}/tháng**. Hành động là tự động tắt "
        "instance sau khi job kết thúc và right-size GPU dựa trên MFU/MBU.",
    ]

    allocation_lines = [
        f"Tag coverage đạt **{r4['tag_coverage']:.1%}**; cổng chargeback: "
        f"**{'mở' if r4['chargeback_ready'] else 'chưa mở'}**.",
        "",
        "| Team | Chi phí inference (USD/ngày) |",
        "|---|---:|",
    ]
    for team, cost in sorted(r4["by_team"].items(), key=lambda item: -item[1]):
        allocation_lines.append(f"| {team} | ${cost:,.2f} |")
    allocation_lines += [
        "",
        "FOCUS export giúp chuẩn hóa dữ liệu giữa nhiều nhà cung cấp. Chính sách đề xuất "
        "là duy trì showback ngay và chỉ chargeback khi coverage luôn trên 80%.",
    ]

    cache = r2["cache_economics"]
    cache_lines = [
        "### 7.1. Extension — Kinh tế học cache",
        "",
        "| Tier | Lượt đọc trung bình | Điểm hòa vốn | Quyết định |",
        "|---|---:|---:|---|",
    ]
    for tier, values in cache.items():
        cache_lines.append(
            f"| {tier} | {values['avg_reads']:.1f} | > {values['break_even_reads']:.2f} | "
            f"{'Bật cache' if values['enabled'] else 'Không bật'} |"
        )
    cache_lines += [
        "",
        "Dataset không có `cache_key`, nên lượt reuse được ước lượng theo `project + model tier`. "
        "Policy chỉ ghi nhận savings khi số lượt đọc vượt điểm hòa vốn, tránh giả định cache luôn có lợi.",
    ]

    reasoning = r2["reasoning_budget"]
    reasoning_lines = [
        "### 7.2. Extension — Ngân sách reasoning",
        "",
        f"Reasoning chiếm **{reasoning['traffic_pct']:.1f}% traffic** nhưng tạo ra "
        f"**{reasoning['cost_share_pct']:.1f}% chi phí inference** và "
        f"**{reasoning['energy_share_pct']:.1f}% điện năng**. Nguyên nhân là output dài hơn "
        "và hệ số năng lượng reasoning được mô phỏng ở mức 80×.",
        "",
        f"Nếu giới hạn reasoning còn **{reasoning['cap_pct']:.0f}% traffic**, giữ các request "
        "có tổng token cao nhất làm proxy độ phức tạp, mô hình tiết kiệm "
        f"**${reasoning['dollar_savings_daily']:,.2f}/ngày** "
        f"(**${reasoning['dollar_savings_daily'] * DAYS:,.0f}/tháng**) và "
        f"**{reasoning['energy_savings_wh_daily']:,.1f} Wh/ngày**.",
        "",
        "Routing rule đề xuất: chỉ bật reasoning khi bộ phân loại độ phức tạp đánh dấu task "
        "ở mức cao hoặc confidence của model thường dưới ngưỡng; các trường hợp còn lại dùng model nhỏ.",
    ]

    carbon = r3["carbon_schedule"]
    carbon_lines = [
        "### 7.3. Extension — Lập lịch nhận thức carbon",
        "",
        f"Các job có thể gián đoạn tiêu thụ ước tính **{carbon['total_energy_kwh']:,.1f} kWh**. "
        f"Chuyển từ `{carbon['current_region']}` sang `{carbon['cleanest_region']}` giảm "
        f"**{carbon['carbon_saved_kg']:,.2f} kgCO2e ({carbon['carbon_reduction_pct']:.1f}%)** "
        f"và thay đổi chi phí điện **${carbon['electricity_savings_usd']:,.2f}**.",
        "",
        f"- Rẻ nhất theo giá điện: **{carbon['cheapest_region']}**.",
        f"- Sạch nhất theo carbon: **{carbon['cleanest_region']}**.",
        f"- Cân bằng chi phí–carbon: **{carbon['balanced_region']}**.",
        "- Cần kiểm tra thêm latency, data residency và khả năng cung cấp GPU trước khi chuyển vùng.",
    ]

    recommendations = [
        "1. **Ưu tiên 1 — xử lý lãng phí tức thời:** tắt GPU idle và điều tra các GPU có MFU thấp; đây là thay đổi nhanh, rủi ro thấp.",
        "2. **Ưu tiên 2 — tối ưu inference:** triển khai cascade, cache có kiểm tra hòa vốn, batch cho traffic không yêu cầu real-time và cap reasoning.",
        "3. **Ưu tiên 3 — tối ưu mua và quản trị:** dùng spot cho job checkpointable, reserved cho tải ổn định; duy trì tag coverage trên 80% trước chargeback.",
        "",
        "Thứ tự trên ưu tiên ROI và khả năng hoàn tác. Reserved 3 năm chỉ nên ký sau khi đo duty cycle đủ dài; "
        "không dùng savings mô phỏng như cam kết tài chính mà chưa re-baseline giá thực tế.",
    ]

    return [
        {"title": "5. Kiểm toán hiệu quả GPU và GPU-Util lie", "lines": lie_lines},
        {"title": "6. Phân bổ chi phí và chargeback", "lines": allocation_lines},
        {"title": "7. Các phần mở rộng đã thực hiện", "lines": cache_lines + [""] + reasoning_lines + [""] + carbon_lines},
        {"title": "8. Khuyến nghị ưu tiên cho NimbusAI", "lines": recommendations},
    ]


def _build_writeup(r1: dict, r2: dict, r3: dict, r5: dict) -> str:
    reasoning = r2["reasoning_budget"]
    carbon = r3["carbon_schedule"]
    largest = max(r5["levers"].items(), key=lambda item: item[1])
    return f"""# Bài viết ngắn — Tối ưu Chi phí GPU cho NimbusAI

## Baseline và kết quả tối ưu

Chi phí cơ sở của mô phỏng là **${r5['baseline_monthly']:,.0f}/tháng**. Sau khi áp dụng các đòn bẩy FinOps, chi phí còn **${r5['optimized_monthly']:,.0f}/tháng**, tiết kiệm **{r5['total_savings_pct']:.1f}%**. Riêng inference giảm từ **${r2['baseline_per_m']:.3f}/1M-token** xuống **${r2['optimized_per_m']:.3f}/1M-token**, tương đương giảm **{r2['savings_pct']:.1f}%**.

Đòn bẩy đóng góp nhiều nhất là **{largest[0]}**, tiết kiệm khoảng **${largest[1]:,.0f}/tháng**. Kết quả cho thấy cần đo cả đầu ra token thay vì chỉ tối ưu giá thuê GPU theo giờ.

## GPU-Util lie

`gpu-h100-4` báo GPU-Util gần 98% nhưng MFU chỉ khoảng 20%. GPU-Util chỉ đo thời gian thiết bị bận; memory stall, chờ dữ liệu và kernel overhead vẫn làm đồng hồ hoạt động mà không tạo nhiều FLOPs hữu ích. Vì vậy dùng GPU-Util một mình có thể che giấu over-provisioning. Fleet còn tạo ra **${r1['idle_waste_daily'] * DAYS:,.0f}/tháng** chi phí idle.

## Các phần mở rộng

Kinh tế học cache được bổ sung bằng điểm hòa vốn theo số lượt đọc. Cache chỉ được tính savings khi reuse thực tế ước lượng vượt ngưỡng, tránh áp dụng cache mù quáng.

Reasoning hiện chiếm **{reasoning['traffic_pct']:.1f}% traffic**, **{reasoning['cost_share_pct']:.1f}% chi phí** và **{reasoning['energy_share_pct']:.1f}% điện năng**. Cap reasoning ở {reasoning['cap_pct']:.0f}% traffic có thể tiết kiệm **${reasoning['dollar_savings_daily'] * DAYS:,.0f}/tháng** và **{reasoning['energy_savings_wh_daily']:,.1f} Wh/ngày** trong mô phỏng.

Lập lịch carbon cho thấy chuyển workload interruptible từ `{carbon['current_region']}` sang `{carbon['cleanest_region']}` có thể giảm **{carbon['carbon_saved_kg']:,.2f} kgCO2e**, tương đương **{carbon['carbon_reduction_pct']:.1f}%**. Quyết định production vẫn phải cân bằng latency và data residency.

## Ba hành động ưu tiên

1. Tự động tắt GPU idle, theo dõi MFU/MBU và right-size các GPU có hiệu quả thấp.
2. Triển khai cascade, prompt cache có kiểm tra hòa vốn, batch API và ngân sách reasoning.
3. Chuyển job checkpointable sang spot, tải ổn định sang reserved sau khi vượt điểm hòa vốn; giữ tag coverage trên 80% trước chargeback.

Các con số sử dụng snapshot giá tháng 06/2026 và dữ liệu tổng hợp seed 25, vì vậy cần re-baseline trước khi áp dụng thực tế.
"""


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    r4 = m4_allocation.run(verbose=False)
    cat = catalog_by_type()

    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]
    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        current = lie["gpu_type"]
        target = RIGHTSIZE_MAP.get(current, current)
        delta = num(cat[current]["on_demand_hr"]) - num(cat[target]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference: cascade/cache/batch": round(infer_savings),
        "Mua GPU: spot/reserved": round(purchasing_savings),
        "Right-size GPU hiệu quả thấp": round(rightsize_savings),
        "Tắt GPU idle": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    carbon_schedule = r3["carbon_schedule"]
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": carbon_schedule["cleanest_region"],
        "cheapest_region": carbon_schedule["cheapest_region"],
        "balanced_region": carbon_schedule["balanced_region"],
    }
    unit_economics = {
        "baseline_per_m": r2["baseline_per_m"],
        "optimized_per_m": r2["optimized_per_m"],
        "savings_pct": r2["savings_pct"],
    }

    md = report.build_report(
        baseline,
        optimized,
        levers,
        sustainability=sust,
        unit_economics=unit_economics,
        extra_sections=_extra_sections(r1, r2, r3, r4),
        language="vi",
    )
    out_dir = os.path.join(ROOT, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_md = os.path.join(out_dir, "report.md")
    with open(out_md, "w", encoding="utf-8", newline="\n") as file:
        file.write(md)
    writeup = _build_writeup(
        r1,
        r2,
        r3,
        {
            "baseline_monthly": round(baseline),
            "optimized_monthly": round(optimized),
            "levers": levers,
            "total_savings_pct": round(total_pct, 1),
        },
    )
    with open(os.path.join(out_dir, "writeup_vi.md"), "w", encoding="utf-8", newline="\n") as file:
        file.write(writeup)
    png = report.savings_waterfall(
        levers,
        os.path.join(out_dir, "savings.png"),
        language="vi",
    )

    if verbose:
        print("== M5 Báo cáo Tối ưu ==")
        print(md)
        suffix = " + outputs/savings.png" if png else " (thiếu matplotlib: bỏ qua PNG)"
        print(f"\nĐã ghi: outputs/report.md + outputs/writeup_vi.md{suffix}")

    return {
        "baseline_monthly": round(baseline),
        "optimized_monthly": round(optimized),
        "levers": levers,
        "total_savings_pct": round(total_pct, 1),
        "unit_economics": unit_economics,
    }


if __name__ == "__main__":
    run()
