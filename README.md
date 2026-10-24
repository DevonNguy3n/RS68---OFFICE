# RS68 Office

Văn phòng Content AI chạy local với giao diện 3D xoay/zoom, quản lý agent, task và quy trình QC. Bản đầu tiên dùng ChatGPT cho mọi vai trò; tích hợp API AI thật sẽ được thêm ở mốc kế tiếp. Không nhập cookie hoặc API key vào mã nguồn.

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

Mở hồ sơ task để dùng luồng nguồn → bản nháp → QC. Chế độ mẫu cho phép kiểm thử mà không gọi API AI. Để dùng OpenAI thật, đặt `OPENAI_API_KEY` và tùy chọn `OPENAI_MODEL` trong môi trường của terminal chạy Backend, rồi bỏ chọn **Chế độ mẫu**. Không đưa khóa vào repo hoặc trình duyệt. API gọi Responses API theo [tài liệu chính thức của OpenAI](https://developers.openai.com/api/docs/guides/text?lang=python).

Nội dung tin tức cần nguồn đã xác minh; AI không tự xuất bản. Nội dung truyện AI cần được ghi rõ là hư cấu. Kết quả AI và checklist vẫn cần người dùng kiểm tra trước khi phê duyệt.

## Kiểm tra

```powershell
python -m unittest -v test_api.py
npm run build
```
