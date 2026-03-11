# Installation Guide

This guide helps you install and run `RAG-Parser-v2` on Windows (with notes for Linux/macOS).

## 1) Prerequisites

- Python `3.10+` (recommended: `3.11`)
- Git
- PostgreSQL `14+` (local instance)
- Ollama (running locally or reachable over network)

Optional but useful:
- VS Code + Python extension

---

## 2) Clone and open project

```bash
git clone <your-repo-url>
cd RAG-Parser-v2
```

If you already have the folder, open it directly in your editor.

---

## 3) Create and activate virtual environment

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### Windows (cmd)

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

---

## 4) Install Python dependencies

Install what is already listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Install additional runtime packages used by the current codebase:

```bash
pip install streamlit plotly sqlalchemy psycopg2-binary pgvector openpyxl numpy requests langchain-community langchain-text-splitters langchain-ollama
```

If you process legacy Excel `.xls` files, also install:

```bash
pip install xlrd
```

If `torch` is missing when starting the dashboard:

```bash
pip install torch
```

---

## 5) Configure PostgreSQL

The project currently uses this connection in code:

`postgresql+psycopg2://postgres:postgres@localhost:5432/reportdb`

Set up PostgreSQL accordingly:

1. Ensure PostgreSQL service is running.
2. Create database:

```sql
CREATE DATABASE reportdb;
```

3. Ensure user/password in PostgreSQL match the connection string, **or** update the connection string in `Persist_Handler.py`.

> Tables are auto-created when `Persist_Handler` initializes.

---

## 6) Configure Ollama and models

The project expects:
- Embedding model: `nomic-embed-text` (see `get_embedding_function.py`)
- Chat model: `qwen2.5-coder:32b` with base URL in `LLM_Handler.py`

Install/pull models:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5-coder:32b
```

Then run Ollama server (if not already running):

```bash
ollama serve
```

If your Ollama host is different, update `base_url` in `LLM_Handler.py`.

---

## 7) First run

### Run Streamlit dashboard

```bash
streamlit run Report_Dashboard.py --server.port 10056
```

Open browser at:

`http://localhost:10056`

### Optional: build/query Chroma DB (RAG scripts)

```bash
python populate_database.py --reset
python query_data.py "your question"
```

---

## 8) Verify installation

Run a quick smoke test:

```bash
python -c "import streamlit, plotly, sqlalchemy, psycopg2, openpyxl, langchain_community; print('OK')"
```

Run tests (if available/maintained):

```bash
pytest -q
```

---

## 9) Common issues

- **`ModuleNotFoundError`**: install missing package in active `.venv`.
- **PostgreSQL connection errors**: verify DB exists, credentials, host, and port.
- **Ollama timeout/connection errors**: check Ollama is running and model is pulled.
- **`.xls` read errors**: install `xlrd`.
- **Port in use for Streamlit**: change port (`--server.port 10057`).

---

## 10) Recommended next cleanup (optional)

- Move DB URL and Ollama URL/model names to environment variables.
- Add all required packages to `requirements.txt` for one-command install.
- Add a `.env.example` file for local setup consistency.
