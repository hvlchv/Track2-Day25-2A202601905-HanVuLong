# Báo cáo Tối ưu Chi phí GPU — NimbusAI

## 1. Tóm tắt điều hành

**Kỳ phân tích:** Theo tháng  
**Chi phí cơ sở:** $27,133  
**Chi phí sau tối ưu:** $14,626  
**Tiết kiệm dự kiến:** $12,507 (**46.1%**)

Kết quả đạt mục tiêu giảm tối thiểu 40% chi phí. Đơn vị kinh tế chính là USD trên một triệu token, thay vì chỉ nhìn USD trên giờ GPU.

## 2. Hiệu quả theo $/1M-token

| Chỉ số | Baseline | Sau tối ưu | Mức giảm |
|---|---:|---:|---:|
| $/1M-token | $6.488 | $1.126 | 82.6% |

## 3. Tiết kiệm theo từng đòn bẩy

| Đòn bẩy | Tiết kiệm (USD/tháng) | Tỷ trọng |
|---|---:|---:|
| Inference: cascade/cache/batch | $1,212 | 9.7% |
| Mua GPU: spot/reserved | $10,040 | 80.3% |
| Right-size GPU hiệu quả thấp | $655 | 5.2% |
| Tắt GPU idle | $600 | 4.8% |

## 4. Tính bền vững

- Năng lượng cho truy vấn mẫu: 0.24 Wh.
- Phát thải tại us-east-1: 0.091 gCO2e/truy vấn.
- Vùng sạch nhất: **europe-north1**.
- Vùng có giá điện thấp nhất: **us-east-wa**.
- Vùng cân bằng chi phí–carbon: **europe-north1**.

## 5. Kiểm toán hiệu quả GPU và GPU-Util lie

- **gpu-h100-4 (H100)**: GPU-Util 98.2% nhưng MFU chỉ 19.4%.
- **gpu-a10g-1 (A10G)**: GPU-Util 96.9% nhưng MFU chỉ 26.8%.

GPU-Util của `nvidia-smi` đo tỷ lệ thời gian clock GPU có hoạt động, không đo lượng FLOPs hữu ích. Memory stall, chờ I/O hoặc kernel nhỏ vẫn có thể làm GPU báo bận gần 100% trong khi chỉ khai thác một phần năng lực tính toán.

Chi phí idle đo được là **$20.00/ngày**, tương đương **$600/tháng**. Hành động là tự động tắt instance sau khi job kết thúc và right-size GPU dựa trên MFU/MBU.

## 6. Phân bổ chi phí và chargeback

Tag coverage đạt **91.8%**; cổng chargeback: **mở**.

| Team | Chi phí inference (USD/ngày) |
|---|---:|
| assistant | $2.59 |
| search | $2.49 |
| eval | $1.79 |
| rag | $1.60 |

FOCUS export giúp chuẩn hóa dữ liệu giữa nhiều nhà cung cấp. Chính sách đề xuất là duy trì showback ngay và chỉ chargeback khi coverage luôn trên 80%.

## 7. Các phần mở rộng đã thực hiện

### 7.1. Extension — Kinh tế học cache

| Tier | Lượt đọc trung bình | Điểm hòa vốn | Quyết định |
|---|---:|---:|---|
| small | 237.8 | > 1.39 | Bật cache |
| large | 62.2 | > 1.39 | Bật cache |

Dataset không có `cache_key`, nên lượt reuse được ước lượng theo `project + model tier`. Policy chỉ ghi nhận savings khi số lượt đọc vượt điểm hòa vốn, tránh giả định cache luôn có lợi.

### 7.2. Extension — Ngân sách reasoning

Reasoning chiếm **8.4% traffic** nhưng tạo ra **16.5% chi phí inference** và **94.0% điện năng**. Nguyên nhân là output dài hơn và hệ số năng lượng reasoning được mô phỏng ở mức 80×.

Nếu giới hạn reasoning còn **5% traffic**, giữ các request có tổng token cao nhất làm proxy độ phức tạp, mô hình tiết kiệm **$0.24/ngày** (**$7/tháng**) và **7,612.0 Wh/ngày**.

Routing rule đề xuất: chỉ bật reasoning khi bộ phân loại độ phức tạp đánh dấu task ở mức cao hoặc confidence của model thường dưới ngưỡng; các trường hợp còn lại dùng model nhỏ.

### 7.3. Extension — Lập lịch nhận thức carbon

Các job có thể gián đoạn tiêu thụ ước tính **1,789.0 kWh**. Chuyển từ `us-east-1` sang `europe-north1` giảm **626.15 kgCO2e (92.1%)** và thay đổi chi phí điện **$53.67**.

- Rẻ nhất theo giá điện: **us-east-wa**.
- Sạch nhất theo carbon: **europe-north1**.
- Cân bằng chi phí–carbon: **europe-north1**.
- Cần kiểm tra thêm latency, data residency và khả năng cung cấp GPU trước khi chuyển vùng.

## 8. Khuyến nghị ưu tiên cho NimbusAI

1. **Ưu tiên 1 — xử lý lãng phí tức thời:** tắt GPU idle và điều tra các GPU có MFU thấp; đây là thay đổi nhanh, rủi ro thấp.
2. **Ưu tiên 2 — tối ưu inference:** triển khai cascade, cache có kiểm tra hòa vốn, batch cho traffic không yêu cầu real-time và cap reasoning.
3. **Ưu tiên 3 — tối ưu mua và quản trị:** dùng spot cho job checkpointable, reserved cho tải ổn định; duy trì tag coverage trên 80% trước chargeback.

Thứ tự trên ưu tiên ROI và khả năng hoàn tác. Reserved 3 năm chỉ nên ký sau khi đo duty cycle đủ dài; không dùng savings mô phỏng như cam kết tài chính mà chưa re-baseline giá thực tế.

---

*Các mức giá là snapshot tháng 06/2026. Cần thiết lập lại baseline trước khi áp dụng vào môi trường thực tế.*