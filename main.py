#!/usr/bin/env python3
"""
Claude Usage Dashboard - FastAPI app to track OpenClaw/Claude usage
"""
import json
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Claude Usage Dashboard")

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# OpenClaw sessions directory
OPENCLAW_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"


def parse_session_file(filepath: Path) -> dict:
    """Parse a session JSONL file and extract usage data."""
    session_data = {
        "id": None,
        "start_time": None,
        "messages": 0,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read": 0,
            "cache_write": 0,
            "total_tokens": 0,
            "cost": 0.0,
        },
        "models": defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0}),
        "requests": [],
    }
    
    current_model = "unknown"
    
    try:
        with open(filepath, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_type = entry.get("type")
                    
                    if entry_type == "session":
                        session_data["id"] = entry.get("id")
                        session_data["start_time"] = entry.get("timestamp")
                    
                    elif entry_type == "model_change":
                        current_model = entry.get("modelId", "unknown")
                    
                    elif entry_type == "message":
                        msg = entry.get("message", {})
                        if msg.get("role") == "user":
                            session_data["messages"] += 1
                    
                    elif entry_type == "assistant_response":
                        usage = entry.get("usage", {})
                        cost_data = usage.get("cost", {})
                        
                        input_tokens = usage.get("input", 0)
                        output_tokens = usage.get("output", 0)
                        cache_read = usage.get("cacheRead", 0)
                        cache_write = usage.get("cacheWrite", 0)
                        total = usage.get("totalTokens", 0)
                        cost = cost_data.get("total", 0.0)
                        
                        session_data["usage"]["input_tokens"] += input_tokens
                        session_data["usage"]["output_tokens"] += output_tokens
                        session_data["usage"]["cache_read"] += cache_read
                        session_data["usage"]["cache_write"] += cache_write
                        session_data["usage"]["total_tokens"] += total
                        session_data["usage"]["cost"] += cost
                        
                        # Track per-model usage
                        session_data["models"][current_model]["calls"] += 1
                        session_data["models"][current_model]["tokens"] += total
                        session_data["models"][current_model]["cost"] += cost
                        
                        # Track individual requests for timeline
                        session_data["requests"].append({
                            "timestamp": entry.get("timestamp"),
                            "model": current_model,
                            "tokens": total,
                            "cost": cost,
                        })
                        
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    
    # Convert defaultdict to regular dict
    session_data["models"] = dict(session_data["models"])
    return session_data


def get_all_usage() -> dict:
    """Aggregate usage from all session files."""
    total_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_write": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }
    models = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
    sessions = []
    all_requests = []
    daily_usage = defaultdict(lambda: {"tokens": 0, "cost": 0.0, "requests": 0})
    
    if not OPENCLAW_SESSIONS_DIR.exists():
        return {
            "total": total_usage,
            "models": {},
            "sessions": [],
            "daily": {},
            "requests": [],
        }
    
    for session_file in OPENCLAW_SESSIONS_DIR.glob("*.jsonl"):
        session_data = parse_session_file(session_file)
        
        if session_data["id"]:
            sessions.append({
                "id": session_data["id"][:8],
                "start_time": session_data["start_time"],
                "messages": session_data["messages"],
                "tokens": session_data["usage"]["total_tokens"],
                "cost": session_data["usage"]["cost"],
            })
        
        # Aggregate totals
        for key in total_usage:
            total_usage[key] += session_data["usage"].get(key, 0)
        
        # Aggregate models
        for model, data in session_data["models"].items():
            models[model]["calls"] += data["calls"]
            models[model]["tokens"] += data["tokens"]
            models[model]["cost"] += data["cost"]
        
        # Aggregate requests for timeline
        for req in session_data["requests"]:
            all_requests.append(req)
            if req["timestamp"]:
                day = req["timestamp"][:10]
                daily_usage[day]["tokens"] += req["tokens"]
                daily_usage[day]["cost"] += req["cost"]
                daily_usage[day]["requests"] += 1
    
    # Sort requests by timestamp
    all_requests.sort(key=lambda x: x["timestamp"] or "")
    
    # Sort daily usage
    sorted_daily = dict(sorted(daily_usage.items()))
    
    return {
        "total": total_usage,
        "models": dict(models),
        "sessions": sorted(sessions, key=lambda x: x["start_time"] or "", reverse=True),
        "daily": sorted_daily,
        "requests": all_requests[-100:],  # Last 100 requests
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    usage = get_all_usage()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usage": usage,
        "now": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    })


@app.get("/api/usage")
async def api_usage():
    """JSON API endpoint for usage data."""
    return get_all_usage()


@app.get("/api/refresh")
async def api_refresh():
    """Refresh and return latest usage data."""
    return get_all_usage()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=500)
