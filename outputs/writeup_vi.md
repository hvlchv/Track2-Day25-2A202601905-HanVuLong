# Bài viết ngắn — Tối ưu Chi phí GPU cho NimbusAI

## Baseline và kết quả tối ưu

Chi phí cơ sở của mô phỏng là **$27,133/tháng**. Sau khi áp dụng các đòn bẩy FinOps, chi phí còn **$14,626/tháng**, tiết kiệm **46.1%**. Riêng inference giảm từ **$6.488/1M-token** xuống **$1.126/1M-token**, tương đương giảm **82.6%**.

Đòn bẩy đóng góp nhiều nhất là **Mua GPU: spot/reserved**, tiết kiệm khoảng **$10,040/tháng**. Kết quả cho thấy cần đo cả đầu ra token thay vì chỉ tối ưu giá thuê GPU theo giờ.

## GPU-Util lie

`gpu-h100-4` báo GPU-Util gần 98% nhưng MFU chỉ khoảng 20%. GPU-Util chỉ đo thời gian thiết bị bận; memory stall, chờ dữ liệu và kernel overhead vẫn làm đồng hồ hoạt động mà không tạo nhiều FLOPs hữu ích. Vì vậy dùng GPU-Util một mình có thể che giấu over-provisioning. Fleet còn tạo ra **$600/tháng** chi phí idle.

## Các phần mở rộng

Kinh tế học cache được bổ sung bằng điểm hòa vốn theo số lượt đọc. Cache chỉ được tính savings khi reuse thực tế ước lượng vượt ngưỡng, tránh áp dụng cache mù quáng.

Reasoning hiện chiếm **8.4% traffic**, **16.5% chi phí** và **94.0% điện năng**. Cap reasoning ở 5% traffic có thể tiết kiệm **$7/tháng** và **7,612.0 Wh/ngày** trong mô phỏng.

Lập lịch carbon cho thấy chuyển workload interruptible từ `us-east-1` sang `europe-north1` có thể giảm **626.15 kgCO2e**, tương đương **92.1%**. Quyết định production vẫn phải cân bằng latency và data residency.

## Ba hành động ưu tiên

1. Tự động tắt GPU idle, theo dõi MFU/MBU và right-size các GPU có hiệu quả thấp.
2. Triển khai cascade, prompt cache có kiểm tra hòa vốn, batch API và ngân sách reasoning.
3. Chuyển job checkpointable sang spot, tải ổn định sang reserved sau khi vượt điểm hòa vốn; giữ tag coverage trên 80% trước chargeback.

Các con số sử dụng snapshot giá tháng 06/2026 và dữ liệu tổng hợp seed 25, vì vậy cần re-baseline trước khi áp dụng thực tế.
