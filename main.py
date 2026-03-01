#!/usr/bin/env python3
"""
Claude Pro Usage Dashboard - Track your Claude Pro subscription usage locally
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Claude Pro Usage Dashboard")

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# OpenClaw sessions directory
OPENCLAW_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"

# Claude Pro limits (approximate - Anthropic doesn't publish exact numbers)
CLAUDE_PRO_LIMITS = {
    "messages_per_day": 100,  # Approximate daily limit
    "messages_per_hour": 25,  # Approximate hourly limit
}


def parse_session_file(filepath: Path) -> dict:
    """Parse a session JSONL file and extract conversation data."""
    session_data = {
        "id": None,
        "start_time": None,
        "end_time": None,
        "user_messages": 0,
        "assistant_messages": 0,
        "models": defaultdict(int),
        "messages": [],  # Individual message timestamps
        "conversations": [],  # Message pairs
    }
    
    current_model = "claude"
    last_user_msg = None
    
    try:
        with open(filepath, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_type = entry.get("type")
                    timestamp = entry.get("timestamp")
                    
                    if entry_type == "session":
                        session_data["id"] = entry.get("id")
                        session_data["start_time"] = timestamp
                    
                    elif entry_type == "model_change":
                        current_model = entry.get("modelId", "claude")
                    
                    elif entry_type == "message":
                        msg = entry.get("message", {})
                        role = msg.get("role")
                        
                        if role == "user":
                            session_data["user_messages"] += 1
                            content = msg.get("content", [])
                            text = ""
                            if isinstance(content, list):
                                for c in content:
                                    if isinstance(c, dict) and c.get("type") == "text":
                                        text = c.get("text", "")[:100]
                                        break
                            elif isinstance(content, str):
                                text = content[:100]
                            
                            # Clean up metadata prefix from preview
                            if "```" in text:
                                parts = text.split("```")
                                if len(parts) >= 3:
                                    text = parts[-1].strip()[:100]
                            
                            last_user_msg = {
                                "timestamp": timestamp,
                                "preview": text,
                                "model": current_model,
                            }
                            session_data["messages"].append({
                                "timestamp": timestamp,
                                "type": "user",
                                "model": current_model,
                            })
                        
                        elif role == "assistant":
                            # Get model from message if available
                            msg_model = msg.get("model", current_model)
                            if msg_model:
                                current_model = msg_model
                            
                            session_data["assistant_messages"] += 1
                            session_data["models"][current_model] += 1
                            session_data["end_time"] = timestamp
                            
                            session_data["messages"].append({
                                "timestamp": timestamp,
                                "type": "assistant", 
                                "model": current_model,
                            })
                            
                            if last_user_msg:
                                session_data["conversations"].append({
                                    "timestamp": last_user_msg["timestamp"],
                                    "preview": last_user_msg["preview"],
                                    "model": current_model,
                                })
                                last_user_msg = None
                        
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    
    session_data["models"] = dict(session_data["models"])
    return session_data


def get_all_usage() -> dict:
    """Aggregate usage from all session files for Pro subscription tracking."""
    now = datetime.utcnow()
    today = now.date()
    hour_ago = now - timedelta(hours=1)
    
    stats = {
        "total_conversations": 0,
        "total_user_messages": 0,
        "total_assistant_messages": 0,
        "today_messages": 0,
        "hour_messages": 0,
        "models": defaultdict(int),
        "daily": defaultdict(lambda: {"messages": 0, "conversations": 0}),
        "hourly_today": defaultdict(int),
        "sessions": [],
        "recent_conversations": [],
    }
    
    if not OPENCLAW_SESSIONS_DIR.exists():
        return {
            "stats": stats,
            "limits": CLAUDE_PRO_LIMITS,
            "usage_percent": {"daily": 0, "hourly": 0},
        }
    
    all_conversations = []
    
    for session_file in OPENCLAW_SESSIONS_DIR.glob("*.jsonl"):
        session_data = parse_session_file(session_file)
        
        if session_data["id"]:
            stats["sessions"].append({
                "id": session_data["id"][:8],
                "start_time": session_data["start_time"],
                "end_time": session_data["end_time"],
                "user_messages": session_data["user_messages"],
                "assistant_messages": session_data["assistant_messages"],
            })
        
        stats["total_user_messages"] += session_data["user_messages"]
        stats["total_assistant_messages"] += session_data["assistant_messages"]
        stats["total_conversations"] += len(session_data["conversations"])
        
        # Aggregate models
        for model, count in session_data["models"].items():
            stats["models"][model] += count
        
        # Process messages for time-based stats
        for msg in session_data["messages"]:
            if msg["type"] == "assistant" and msg["timestamp"]:
                try:
                    msg_time = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                    msg_date = msg_time.date()
                    
                    # Daily stats
                    day_key = msg_date.isoformat()
                    stats["daily"][day_key]["messages"] += 1
                    
                    # Today's messages
                    if msg_date == today:
                        stats["today_messages"] += 1
                        hour_key = msg_time.hour
                        stats["hourly_today"][hour_key] += 1
                    
                    # Last hour
                    if msg_time.replace(tzinfo=None) > hour_ago:
                        stats["hour_messages"] += 1
                        
                except (ValueError, TypeError):
                    pass
        
        # Collect conversations
        all_conversations.extend(session_data["conversations"])
    
    # Sort and limit recent conversations
    all_conversations.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    stats["recent_conversations"] = all_conversations[:20]
    
    # Calculate daily conversations
    for conv in all_conversations:
        if conv["timestamp"]:
            day_key = conv["timestamp"][:10]
            stats["daily"][day_key]["conversations"] += 1
    
    # Sort daily
    stats["daily"] = dict(sorted(stats["daily"].items()))
    stats["hourly_today"] = dict(sorted(stats["hourly_today"].items()))
    stats["models"] = dict(stats["models"])
    
    # Sort sessions
    stats["sessions"] = sorted(
        stats["sessions"], 
        key=lambda x: x["start_time"] or "", 
        reverse=True
    )
    
    # Calculate usage percentages
    daily_percent = min(100, (stats["today_messages"] / CLAUDE_PRO_LIMITS["messages_per_day"]) * 100)
    hourly_percent = min(100, (stats["hour_messages"] / CLAUDE_PRO_LIMITS["messages_per_hour"]) * 100)
    
    return {
        "stats": stats,
        "limits": CLAUDE_PRO_LIMITS,
        "usage_percent": {
            "daily": round(daily_percent, 1),
            "hourly": round(hourly_percent, 1),
        },
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    data = get_all_usage()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "data": data,
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


@app.get("/api/limits")
async def api_limits():
    """Get current limits configuration."""
    return CLAUDE_PRO_LIMITS


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
