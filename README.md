# Claude Usage Dashboard 🦈

A FastAPI dashboard to track your local OpenClaw/Claude API usage.

![Dashboard Preview](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat&logo=python&logoColor=white)

## Features

- 💰 **Total cost tracking** - See how much you've spent
- 🔢 **Token breakdown** - Input, output, cache read/write
- 🤖 **Per-model stats** - Usage breakdown by Claude model
- 📊 **Daily usage chart** - Visualize usage over time
- 📋 **Session history** - View all sessions with details
- 🔄 **Live refresh** - Real-time data from session files

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/claude-usage-dashboard.git
cd claude-usage-dashboard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the dashboard
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 5000
```

Then open http://localhost:5000 in your browser.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard HTML page |
| `GET /api/usage` | JSON usage data |
| `GET /api/refresh` | Refresh and return latest data |

## Configuration

The dashboard reads session data from:
```
~/.openclaw/agents/main/sessions/*.jsonl
```

Modify `OPENCLAW_SESSIONS_DIR` in `main.py` if your sessions are elsewhere.

## Tech Stack

- **FastAPI** - Modern Python web framework
- **Jinja2** - HTML templating
- **TailwindCSS** - Styling (via CDN)
- **Chart.js** - Usage charts

## License

MIT
