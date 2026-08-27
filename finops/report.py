"""Report assembly — baseline vs optimized, phân tích và biểu đồ savings."""
from __future__ import annotations


def build_report(
    baseline_usd: float,
    optimized_usd: float,
    levers: dict,
    sustainability: dict | None = None,
    period: str = "monthly",
    unit_economics: dict | None = None,
    extra_sections: list[dict] | None = None,
    language: str = "en",
) -> str:
    """Return a Markdown cost-optimization report.

    Mặc định vẫn là tiếng Anh để tương thích API/test gốc. Mission 5 truyền
    ``language='vi'`` để sinh deliverable tiếng Việt có dấu.
    """
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0

    if language != "vi":
        lines = [
            "# NimbusAI — GPU Cost Optimization Report",
            "",
            f"**Period:** {period}  ",
            f"**Baseline spend:** ${baseline_usd:,.0f}  ",
            f"**Optimized spend:** ${optimized_usd:,.0f}  ",
            f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
            "",
            "## Savings by lever",
            "",
            "| Lever | Savings (USD) |",
            "|---|---|",
        ]
        for name, amount in levers.items():
            lines.append(f"| {name} | ${amount:,.0f} |")
        if sustainability:
            lines += [
                "",
                "## Sustainability",
                "",
                f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
                f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
                f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
            ]
        lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
        return "\n".join(lines)

    period_vi = "tháng" if period == "monthly" else period
    lines = [
        "# Báo cáo Tối ưu Chi phí GPU — NimbusAI",
        "",
        "## 1. Tóm tắt điều hành",
        "",
        f"**Kỳ phân tích:** Theo {period_vi}  ",
        f"**Chi phí cơ sở:** ${baseline_usd:,.0f}  ",
        f"**Chi phí sau tối ưu:** ${optimized_usd:,.0f}  ",
        f"**Tiết kiệm dự kiến:** ${savings:,.0f} (**{pct:.1f}%**)",
        "",
        "Kết quả đạt mục tiêu giảm tối thiểu 40% chi phí. Đơn vị kinh tế chính "
        "là USD trên một triệu token, thay vì chỉ nhìn USD trên giờ GPU.",
    ]
    if unit_economics:
        lines += [
            "",
            "## 2. Hiệu quả theo $/1M-token",
            "",
            "| Chỉ số | Baseline | Sau tối ưu | Mức giảm |",
            "|---|---:|---:|---:|",
            (
                f"| $/1M-token | ${unit_economics.get('baseline_per_m', 0):,.3f} | "
                f"${unit_economics.get('optimized_per_m', 0):,.3f} | "
                f"{unit_economics.get('savings_pct', 0):.1f}% |"
            ),
        ]

    lines += [
        "",
        "## 3. Tiết kiệm theo từng đòn bẩy",
        "",
        "| Đòn bẩy | Tiết kiệm (USD/tháng) | Tỷ trọng |",
        "|---|---:|---:|",
    ]
    total_lever_savings = sum(levers.values())
    for name, amount in levers.items():
        share = amount / total_lever_savings * 100 if total_lever_savings else 0.0
        lines.append(f"| {name} | ${amount:,.0f} | {share:.1f}% |")

    if sustainability:
        lines += [
            "",
            "## 4. Tính bền vững",
            "",
            f"- Năng lượng cho truy vấn mẫu: {sustainability.get('wh_per_query', 0):.2f} Wh.",
            f"- Phát thải tại us-east-1: {sustainability.get('carbon_g', 0):.3f} gCO2e/truy vấn.",
            f"- Vùng sạch nhất: **{sustainability.get('best_region', 'n/a')}**.",
            f"- Vùng có giá điện thấp nhất: **{sustainability.get('cheapest_region', 'n/a')}**.",
            f"- Vùng cân bằng chi phí–carbon: **{sustainability.get('balanced_region', 'n/a')}**.",
        ]

    for section in extra_sections or []:
        lines += ["", f"## {section['title']}", ""]
        lines.extend(section.get("lines", []))

    lines += [
        "",
        "---",
        "",
        "*Các mức giá là snapshot tháng 06/2026. Cần thiết lập lại baseline trước khi áp dụng vào môi trường thực tế.*",
    ]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, language: str = "en") -> str:
    """Write a savings bar chart PNG. Returns path; no-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(names, vals, color="#2e548a")
    ax.set_ylabel("Tiết kiệm (USD / tháng)" if language == "vi" else "Savings (USD / month)")
    ax.set_title("Tiết kiệm chi phí GPU theo đòn bẩy FinOps" if language == "vi" else "GPU cost savings by FinOps lever")
    ax.bar_label(bars, labels=[f"${value:,.0f}" for value in vals], padding=3)
    plt.xticks(rotation=18, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
