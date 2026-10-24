# RS68 Office

Văn phòng Content AI chạy local với giao diện 3D xoay/zoom, bảng điều hành treo tường lấy số liệu SQLite, quản lý agent, task và quy trình QC chéo. Khi chưa đặt `OPENAI_API_KEY`, nhân viên AI không tự chạy; trò chuyện và cuộc họp dùng phản hồi local từ dữ liệu task. Không nhập cookie hoặc API key vào mã nguồn.

## Chạy local

Yêu cầu Node.js 20+, Python 3.11+.

Terminal 1:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn api:app --reload
```

Terminal 2:

```powershell
npm install
npm run dev
```

Truy cập `http://localhost:5173`. API docs ở `http://127.0.0.1:8000/docs`.

Văn phòng cho phép chọn agent, tạo task tin tức Mỹ/truyện AI, lưu nguồn, tạo nhiều phiên bản nội dung, kiểm duyệt độc lập và phê duyệt. Các trạng thái và thao tác được lưu trong audit log SQLite.

Mở hồ sơ task để dùng luồng nguồn → bản nháp → QC. Chế độ mẫu cho phép kiểm thử mà không gọi API AI. Để dùng OpenAI thật, đặt `OPENAI_API_KEY` và tùy chọn `OPENAI_MODEL` trong môi trường của terminal chạy Backend, rồi khởi động lại backend. Không đưa khóa vào repo hoặc trình duyệt. API gọi Responses API theo [tài liệu chính thức của OpenAI](https://developers.openai.com/api/docs/guides/text?lang=python).

### Dùng muse2api local

Backend cũng hỗ trợ [muse2api của DevonNguy3n](https://github.com/DevonNguy3n/muse2api) qua endpoint `/v1/responses`. Chạy muse2api riêng trên máy theo hướng dẫn của repo đó và đăng nhập Muse qua trang quản trị của dịch vụ. Sau đó, trong **terminal chạy RS68 backend**, đặt:

```powershell
$env:AI_PROVIDER = 'muse2api'
$env:AI_BASE_URL = 'http://127.0.0.1:18610/v1'
$env:AI_MODEL = 'muse-spark'
$env:AI_API_KEY = '<khóa API của muse2api>'
uvicorn api:app --reload
```

Khóa này là khóa API do **muse2api** cấp, không phải cookie Muse. Nếu đã đặt `MUSE2API_KEY` trong môi trường, RS68 cũng nhận khóa đó khi `AI_API_KEY` trống. Giữ dịch vụ trên `127.0.0.1`, đặt khóa riêng và không commit cookie, khóa hoặc database tài khoản. RS68 chỉ bật agent khi có khóa; để sinh nội dung thật, dịch vụ muse2api còn phải chạy và có phiên Muse hợp lệ. Kiểm tra cấu hình với `GET /health`. `AI_BASE_URL` và `AI_MODEL` cũng có thể dùng với provider `openai`; mặc định OpenAI giữ nguyên.

Khi có khóa, backend tự xử lý từng bước các task **Đã giao**: nhân viên nghiên cứu → nhân viên viết → leader nội dung → quản lý → phó giám đốc. Ba người review độc lập phải cùng đạt mới chuyển task sang **Đã duyệt**. Tin tức Mỹ phải có nguồn được đánh dấu xác minh trước khi bắt đầu; đánh dấu này do người dùng kiểm tra, AI không tự xác minh sự thật từ Internet. Nếu reviewer yêu cầu sửa, AI có tối đa hai vòng sửa; sau đó cần người dùng xem lại. Mỗi bước được lưu trong hồ sơ task. Nút **Chạy bước tiếp theo** cho phép chạy ngay mà không chờ chu kỳ nền 20 giây. Backend không tự đánh dấu **Hoàn thành** hay đăng Facebook.

Nội dung tin tức cần nguồn đã xác minh; AI không tự xuất bản. Nội dung truyện AI cần được ghi rõ là hư cấu. Kết quả AI và checklist vẫn cần người dùng kiểm tra trước khi phê duyệt.

## Kiểm tra

```powershell
python -m unittest -v test_api.py
npm run build
```
