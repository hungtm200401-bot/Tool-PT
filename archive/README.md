# Tư liệu đã gom lại

- screenshots/: ảnh chụp tham khảo đầy đủ từ thư mục gốc.
- videos/: video gốc được giữ lại.
- diagnostics/: ảnh khảo sát map và dữ liệu chạy thử cũ.

Ứng dụng không đọc thư mục archive. Ảnh bằng chứng lỗi vẫn nằm trong reports/evidence.

Đã bỏ 38 tệp tạm và mã cũ, giải phóng 27.77 MB:
- Cache __pycache__ và các tệp .pyc.
- Khung hình tách từ video trong scratch_video_frames.
- Sáu ảnh cắt tạm: bottom_strip, btn_crop, crop_grid_btn, crop_inner_x, crop_top_right, real_btn.
- Hai script thử thao tác cũ: run_live_test.py, test_protocol_leg.py.
- Hai mô-đun cũ không được mã hiện tại nhập: stuck_detector.py, unstuck_handler.py.

Mã tạo báo cáo HTML đã được chuyển từ reports/html_reporter.py sang core/html_reporter.py.
