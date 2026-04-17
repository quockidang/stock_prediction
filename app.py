from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import shutil
from pathlib import Path
import os
import json
import pandas as pd
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import AsyncOpenAI
import stockout_analysis
from retail_plugins import FMCGSmartPlugin

load_dotenv()

app = FastAPI(
    title="Stockout Analysis API",
    description="API to upload order history and generate analysis results (T-Cycle & MBA) + Agent Chat",
    version="1.1.0"
)

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

plugin = FMCGSmartPlugin()

class ChatRequest(BaseModel):
    message: str
    customer_name: Optional[str] = None
    store_id: Optional[str] = None

@app.get("/api/customers")
async def get_customers():
    customer_file = DATA_DIR / "customer.csv"
    if not customer_file.exists():
        return []
    try:
        df = pd.read_csv(customer_file)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(), status_code=200)
    return {"message": "Welcome to Stockout Analysis API! Visit /upload or create static/index.html."}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    target_path = DATA_DIR / "order_history.csv"
    cycle_file = OUTPUT_DIR / "cycle_time_results.csv"
    mba_file = OUTPUT_DIR / "mba_results.csv"
    
    for f in [target_path, cycle_file, mba_file]:
        if f.exists():
            f.unlink()

    try:
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"🚀 Running analysis on {file.filename}...")
        stockout_analysis.main()
        
        # Reload plugin data
        global plugin
        plugin = FMCGSmartPlugin()
        
        if not cycle_file.exists() or not mba_file.exists():
            return {"status": "partial_success", "message": "Analysis completed, some outputs missing."}

        return {
            "status": "success",
            "outputs": {
                "cycle_time": f"/output/{cycle_file.name}",
                "mba": f"/output/{mba_file.name}"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # Sử dụng Ollama local qua endpoint tương thích OpenAI
    client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    
    context_info = ""
    if req.customer_name and req.store_id:
        context_info = f"\n\nTHÔNG TIN KHÁCH HÀNG ĐANG ĐĂNG NHẬP:\n- Tên khách hàng: {req.customer_name}\n- Mã cửa hàng (store_id) mặc định: {req.store_id}\nHãy NGẦM ĐỊNH sử dụng Mã cửa hàng này cho vào các lệnh gọi hệ thống. KHÔNG CẦN thiết phải hỏi lại khách hàng mã cửa hàng là gì nữa."

    system_prompt = f"""Bạn là Retailer App Agent thông minh hỗ trợ bán lẻ.

QUY TẮC VỀ SUY NGHĨ (BẮT BUỘC):
- Trước mỗi hành động (gọi tool) hoặc trước câu trả lời cuối cùng, bạn PHẢI viết suy nghĩ bằng TIẾNG VIỆT bên trong thẻ <think>...</think>.
- Ví dụ: <think>Tôi cần gọi get_replenishment_suggestions để lấy danh sách hàng cần nhập cho cửa hàng này.</think>

QUY TẮC BẮT BUỘC KHI LÊN ĐƠN HÀNG GỢI Ý:
1. Bạn phải dùng `get_replenishment_suggestions` để lấy danh sách hàng cần nhập.
2. Với các sản phẩm lấy được, hãy gọi tiếp `get_upsell_suggestions` để tìm hàng bán kèm.
3. KHÔNG BAO GIỜ DỪNG LẠI GIỮA CHỪNG. Nếu bạn nói "Tôi sẽ kiểm tra P009", bạn PHẢI phát ra function call ngay lập tức, KHÔNG ĐƯỢC kết thúc lượt trò chuyện.
4. Khi đã có đủ thông tin, hãy trình bày NGAY LẬP TỨC một BẢNG MARKDOWN hoàn chỉnh Đơn hàng gợi ý (Sản phẩm chính + Hàng bán kèm lý tưởng).{context_info}"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message}
    ]
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_replenishment_suggestions",
                "description": "Kiểm tra các sản phẩm sắp hết dựa trên chu kỳ mua hàng của cửa hàng",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "store_id": {"type": "string", "description": "Mã cửa hàng, ví dụ: S001"}
                    },
                    "required": ["store_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_upsell_suggestions",
                "description": "Gợi ý sản phẩm mua kèm dựa trên phân tích giỏ hàng MBA",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_code": {"type": "string", "description": "Mã sản phẩm, ví dụ: P007"}
                    },
                    "required": ["product_code"]
                }
            }
        }
    ]
    try:
        async def event_generator():
            nonlocal messages
            import re
            max_turns = 10
            turn = 0
            try:
                while turn < max_turns:
                    completion = await client.chat.completions.create(
                        model=os.getenv("OLLAMA_MODEL_ID", "gemma4:e4b"),
                        messages=messages,
                        tools=tools,
                        tool_choice="auto",
                        stream=True
                    )

                    full_content = ""
                    tool_calls_data = {}
                    turn_content_buf = ""

                    async for chunk in completion:
                        delta = chunk.choices[0].delta

                        if delta.content:
                            full_content += delta.content
                            turn_content_buf += delta.content

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_calls_data:
                                    tool_calls_data[idx] = {"id": tc.id, "name": "", "arguments": ""}
                                if tc.id:
                                    tool_calls_data[idx]["id"] = tc.id
                                if tc.function and tc.function.name:
                                    if not tool_calls_data[idx]["name"]:
                                        tool_calls_data[idx]["name"] = tc.function.name
                                if tc.function and tc.function.arguments:
                                    tool_calls_data[idx]["arguments"] += tc.function.arguments

                    # Process buffered turn content
                    if turn_content_buf:
                        # Strip <think> blocks and emit as thought events
                        remaining = turn_content_buf
                        processed = ""
                        t_in = False
                        t_buf = ""
                        while remaining:
                            if t_in:
                                end = remaining.find("</think>")
                                if end == -1:
                                    t_buf += remaining
                                    remaining = ""
                                else:
                                    t_buf += remaining[:end]
                                    if t_buf.strip():
                                        yield f"data: {json.dumps({'type': 'thought', 'content': t_buf.strip()})}\n\n"
                                    t_buf = ""
                                    t_in = False
                                    remaining = remaining[end + len("</think>"):]
                            else:
                                start = remaining.find("<think>")
                                if start == -1:
                                    processed += remaining
                                    remaining = ""
                                else:
                                    processed += remaining[:start]
                                    t_in = True
                                    remaining = remaining[start + len("<think>"):]

                        if tool_calls_data and processed.strip():
                            # Content emitted alongside tool calls = pre-tool reasoning
                            yield f"data: {json.dumps({'type': 'thought', 'content': processed.strip()})}\n\n"
                        elif not tool_calls_data and processed.strip():
                            # Final answer turn — split preamble (reasoning) from actual answer
                            import re as _re2
                            # Find where the actual answer starts: first line beginning with #, |, or greeting words
                            answer_start = -1
                            for pat in [r'\n(?=#{1,3}\s)', r'\n(?=\|)', r'\n(?=Chào\b)', r'\n(?=Dựa\b)', r'\n(?=Theo\s+yêu\s+cầu)']:
                                m = _re2.search(pat, processed)
                                if m and (answer_start == -1 or m.start() < answer_start):
                                    answer_start = m.start()
                            if answer_start > 0:
                                preamble = processed[:answer_start].strip()
                                answer = processed[answer_start:].strip()
                                if preamble:
                                    yield f"data: {json.dumps({'type': 'thought', 'content': preamble})}\n\n"
                                if answer:
                                    yield f"data: {json.dumps({'type': 'content', 'delta': answer})}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'content', 'delta': processed})}\n\n"

                    if tool_calls_data:
                        formatted_tool_calls = []
                        for idx, tc in tool_calls_data.items():
                            formatted_tool_calls.append({
                                "id": tc["id"] or f"call_{idx}_{int(os.urandom(4).hex(), 16)}",
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]}
                            })

                        agent_msg = {"role": "assistant", "content": full_content, "tool_calls": formatted_tool_calls}
                        messages.append(agent_msg)

                        for tc in formatted_tool_calls:
                            fname = tc["function"]["name"]
                            args_str = tc["function"]["arguments"]
                            try:
                                fargs = json.loads(args_str)
                            except json.JSONDecodeError:
                                print(f"[Warn] Lỗi phân tích JSON từ Model: {args_str}")
                                fargs = {}
                                for m in re.finditer(r'\{[^{}]*\}', args_str):
                                    try:
                                        fargs = json.loads(m.group(0))
                                        break
                                    except Exception:
                                        continue

                            yield f"data: {json.dumps({'type': 'action', 'content': f'Gọi hàm {fname}({fargs})'})}\n\n"

                            if fname == "get_replenishment_suggestions":
                                obs = plugin.get_replenishment_suggestions(store_id=fargs.get("store_id"))
                                yield f"data: {json.dumps({'type': 'observation', 'content': f'Nhận kết quả: {obs}'})}\n\n"
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "name": fname,
                                    "content": obs
                                })
                                # Auto-chain: call get_upsell_suggestions for each product
                                try:
                                    import ast, re as _re
                                    products = []
                                    if isinstance(obs, list):
                                        raw = obs
                                    else:
                                        m = _re.search(r'\[.*\]', str(obs), _re.DOTALL)
                                        raw = ast.literal_eval(m.group(0)) if m else []
                                    products = [p.get("product_code") for p in raw if isinstance(p, dict) and p.get("product_code")]
                                except Exception:
                                    products = []
                                for prod in products:
                                    upsell_obs = plugin.get_upsell_suggestions(product_code=prod)
                                    upsell_action = f"get_upsell_suggestions({{\"product_code\": \"{prod}\"}})"
                                    yield f"data: {json.dumps({'type': 'action', 'content': f'Gọi hàm {upsell_action}'})}\n\n"
                                    yield f"data: {json.dumps({'type': 'observation', 'content': f'Nhận kết quả: {upsell_obs}'})}\n\n"
                                    import uuid
                                    messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": f"auto_{uuid.uuid4().hex[:8]}", "type": "function", "function": {"name": "get_upsell_suggestions", "arguments": json.dumps({"product_code": prod})}}]})
                                    messages.append({"role": "tool", "tool_call_id": messages[-1]["tool_calls"][0]["id"], "name": "get_upsell_suggestions", "content": upsell_obs})
                            elif fname == "get_upsell_suggestions":
                                obs = plugin.get_upsell_suggestions(product_code=fargs.get("product_code"))
                                yield f"data: {json.dumps({'type': 'observation', 'content': f'Nhận kết quả: {obs}'})}\n\n"
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "name": fname,
                                    "content": obs
                                })
                            else:
                                obs = "Hàm không tồn tại."
                                yield f"data: {json.dumps({'type': 'observation', 'content': f'Nhận kết quả: {obs}'})}\n\n"
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "name": fname,
                                    "content": obs
                                })
                        turn += 1
                    else:
                        break

                yield "data: [DONE]\n\n"

            except Exception as gen_err:
                print(f"[Error] event_generator crashed: {gen_err}")
                yield f"data: {json.dumps({'type': 'error', 'content': str(gen_err)})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
