# Retail AI Agent & Stock Prediction

Dự án này cung cấp hệ thống phân tích quản lý hàng tồn kho, kết hợp với một **AI Assistant (Agent) thông minh** có khả năng tương tác trực tiếp với thông tin bán lẻ. Dự án hoàn toàn bảo mật và có thể chạy offline thông qua Local LLM (Ollama).

## 🚀 Tính năng chính

- **Phân tích T-Cycle (Cycle Time):** Tính toán khoảng thời gian trung bình giữa các lần nhập hàng liên tiếp. Hỗ trợ dự báo thời điểm một cửa hàng nên nhập thêm hàng.
- **Phân tích Giỏ hàng (Market Basket Analysis - MBA):** Khám phá thói quen mua chung của khách hàng (VD: mua sản phẩm A thường mua kèm sản phẩm B) qua các chỉ số Support, Confidence, Lift.
- **AI Retail Agent:** 
  - Chatbot thông minh tự động đọc file Excel/CSV kết quả phân tích.
  - Sử dụng SLM (Ollama / `gemma4:e4b`) hoàn toàn cục bộ, không mất phí API.
  - Hỗ trợ chế độ phản hồi **Thời gian thực (SSE Streaming)** kết hợp Markdown rendering chuẩn xác.
  - Trí tuệ AI có khả năng hiển thị rõ các bước **Suy nghĩ (Thought Process)**, và **Hành động gọi hàm (Tool Calls)** trên giao diện cho phép theo dõi quá trình lên đơn hàng gợi ý.
- **Cá nhân hóa phiên đăng nhập:** Tích hợp giao diện đăng nhập cho phép tùy chọn cửa hàng hoặc người dùng (`login.html`), tự động áp dụng `store_id` vào ngữ cảnh tư vấn và các luồng gọi API.

## 📂 Cấu trúc dự án

```text
stock_prediction/
├── app.py                   # FastAPI server, tích hợp AI chat (Streaming), OpenAI Client trỏ qua Ollama
├── retail_plugins.py        # Các hàm Tool Calls (Plugins) để AI đọc dữ liệu T-Cycle & MBA
├── stockout_analysis.py     # Script Data Processing (Pandas)
├── static/
│   ├── login.html           # Màn hình chọn Khách hàng / Cửa hàng (Giao diện Premium/Glassmorphism)
│   └── index.html           # Màn hình Chat với Agent (Giao diện SSE Streaming + Markdown)
├── data/
│   ├── customer.csv         # Danh sách khách hàng và mã cửa hàng phục vụ màn hình đăng nhập
│   └── order_history.csv    # Dữ liệu gốc
└── output/
    ├── cycle_time_results.csv
    └── mba_results.csv
```

## 📋 Yêu cầu hệ thống

Dự án yêu cầu cài đặt Python 3.8+ và các thư viện:
- `pandas`
- `fastapi`, `uvicorn`
- `openai` (Dùng để giao tiếp với Ollama qua chuẩn OpenAI interface)
- `python-dotenv`
- `semantic-kernel` (Phần lõi Agent)

Đồng thời, bạn phải cài đặt và khởi chạy ứng dụng **[Ollama](https://ollama.com/)** trên máy của mình.

## ⚙️ Hướng dẫn cài đặt và sử dụng

### 1. Khởi động Local LLM với Ollama

Đảm bảo bạn đã pull và chạy mô hình `gemma4:e4b`:
```bash
ollama run gemma4:e4b
```
Quá trình này sẽ mở API nội bộ của Ollama tại cổng `http://localhost:11434`.

### 2. Cài đặt các thư viện Python cần thiết

Mở terminal tại thư mục dự án và chạy:
```bash
pip install pandas fastapi uvicorn semantic-kernel python-dotenv openai
```

### 3. Tự động tính toán số liệu gốc (Tuỳ chọn)

Nếu bạn có tệp tin đơn hàng mới và muốn làm mới bảng gợi ý:
```bash
python stockout_analysis.py
```
Kết quả gợi ý nhập hàng và hàng mua kèm sẽ được tự động tạo và lưu vào thư mục `output/`.

### 4. Khởi chạy Giao diện Tương tác AI (Server API)

Khởi chạy server qua uvicorn:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
Sau đó, hãy truy cập các đường dẫn:
- **Trải nghiệm ứng dụng User:** [http://localhost:8000/static/login.html](http://localhost:8000/static/login.html)
- **API documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

Tại giao diện Web, chọn một tài khoản khách hàng và bắt đầu trò chuyện (VD: *"Hãy tạo cho tôi 1 đơn hàng gợi ý cho hôm nay"*). AI sẽ tự động kích hoạt tiến trình Tool Calls lấy dữ liệu nội bộ và sinh ra kết quả phù hợp nhất!
