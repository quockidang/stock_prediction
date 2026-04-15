# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install dependencies** (no requirements.txt — install manually):
```bash
pip install pandas fastapi uvicorn openai python-dotenv semantic-kernel
```

**Start the local LLM** (required before running the server):
```bash
ollama run gemma4:e4b
```

**Generate analysis outputs** from order data (run whenever `data/order_history.csv` changes):
```bash
python stockout_analysis.py
```

**Start the FastAPI server**:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Access the app**: `http://localhost:8000/static/login.html`
**API docs**: `http://localhost:8000/docs`

## Architecture

### Data pipeline
`data/order_history.csv` → `stockout_analysis.py` → `output/cycle_time_results.csv` + `output/mba_results.csv`

`stockout_analysis.py` runs two analyses:
- **T-Cycle**: Average days between consecutive orders per `(store_id, product_code)`. Lower T_cycle = faster turnover.
- **Market Basket Analysis (MBA)**: Product co-purchase rules per `(store_id, order_date)` basket. Produces support, confidence (A→B and B→A), and lift scores.

### AI agent loop (`app.py`)
`POST /api/chat` accepts `{message, customer_name, store_id}` and runs a streaming tool-calling loop (max 10 turns):
1. Sends messages + tool definitions to Ollama (`http://localhost:11434/v1`, model from `OLLAMA_MODEL_ID` env var, default `gemma4:e4b`).
2. If the model returns `tool_calls`, executes the corresponding plugin method from `retail_plugins.py` and appends the observation to message history.
3. Repeats until the model returns a plain text response.
4. Streams the response via SSE (Server-Sent Events). Thought process (`<think>` tags) is streamed as a separate event type.

### Tool plugins (`retail_plugins.py`)
`FMCGSmartPlugin` has two tools the agent can call:
- `get_replenishment_suggestions(store_id)` — reads `output/cycle_time_results.csv`, returns top 3 products with lowest T_cycle for the store.
- `get_upsell_suggestions(product_code)` — reads `output/mba_results.csv`, returns top 2 complementary products by lift for the given product.

Tool schemas are defined inline in `app.py` (the `tools` list passed to the OpenAI-compatible API).

### Frontend (`static/`)
- `login.html` — fetches `/api/customers` (reads `data/customer.csv`) to populate a dropdown, then redirects to `index.html` with query params.
- `index.html` — chat UI that reads SSE events: `chunk` (text), `thought` (reasoning), `action` (tool call), `observation` (tool result), `done`.

### CSV upload
`POST /upload` accepts a new `order_history.csv`, saves it to `data/`, and automatically re-runs `stockout_analysis.py` to refresh the output files.

## Key data schemas

**`data/order_history.csv`**: `order_id, store_id, product_code, uom_code, quantity, order_date`

**`output/cycle_time_results.csv`**: `store_id, product_code, uom_code, T_cycle, total_orders, total_qty`

**`output/mba_results.csv`**: `product_a, uom_a, product_b, uom_b, support, conf_A_to_B, conf_B_to_A, lift`

**`data/customer.csv`**: maps customer names to store IDs (used by login screen).

## Notes
- `sk_main.py` is a legacy Semantic Kernel demo and is not part of the active application.
- The `.env` file holds an `OPENAI_API_KEY` for fallback, but the app defaults to Ollama locally.
- There are no tests or linting configs in this project.
