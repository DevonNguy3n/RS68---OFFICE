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

Mốc đầu: chọn agent trong văn phòng 3D, tạo task tin tức Mỹ/truyện AI, chuyển trạng thái có kiểm tra điều kiện và audit log. Dữ liệu lưu local bằng SQLite. Mốc tiếp theo sẽ thêm adapter OpenAI, nguồn nghiên cứu, phiên bản nội dung và QC checklist.
