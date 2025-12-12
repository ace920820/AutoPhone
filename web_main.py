"""
Web Interface for AutoPhone Orchestrator
"""
import os
import sys
import io
import asyncio
import json
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv

# Import Registry
from phone_agent.registry import get_agent_by_id

# Fix Windows encoding
if sys.platform.startswith('win'):
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

app = FastAPI(title="AutoPhone Orchestrator Web")
templates = Jinja2Templates(directory="templates")

# Initialize Agent
try:
    agent = get_agent_by_id("phone-orchestrator")
    if not agent:
        print("❌ Error: Could not find 'phone-orchestrator' in registry")
        sys.exit(1)
    print("✅ Orchestrator Agent loaded successfully")
except Exception as e:
    print(f"❌ Failed to load agent: {e}")
    sys.exit(1)


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"Client connected: {websocket.client}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("content")
            
            if not user_message:
                continue

            print(f"Received message: {user_message}")

            # Run agent and stream response
            try:
                # Use agno's run method with stream=True
                # Note: agno's streaming might return different chunk types
                # We need to adapt this based on agno's actual response structure
                
                response_stream = agent.run(user_message, stream=True)
                
                # Check if response_stream is a generator or async generator
                if hasattr(response_stream, '__aiter__'):
                    async for chunk in response_stream:
                        await process_chunk(websocket, chunk)
                else:
                    for chunk in response_stream:
                        await process_chunk(websocket, chunk)

                # Signal end of message
                await websocket.send_json({"type": "end"})

            except Exception as e:
                print(f"Error executing agent: {e}")
                await websocket.send_json({"type": "error", "content": str(e)})
                
    except WebSocketDisconnect:
        print(f"Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

async def process_chunk(websocket: WebSocket, chunk):
    """Process a chunk from the agent and send to websocket"""
    # Debug: print chunk type and content to understand structure
    # print(f"Chunk type: {type(chunk)}")
    
    # Adapt this based on actual Agno chunk structure
    # Usually it's an object with .content or similar
    
    content = ""
    
    # Handle different chunk types from Agno
    if hasattr(chunk, "content"):
        content = chunk.content
    elif isinstance(chunk, str):
        content = chunk
    elif isinstance(chunk, dict) and "content" in chunk:
        content = chunk["content"]
        
    # Check for tool calls if needed (might be in different fields)
    # This is a simplification. Agno's RunResponse/Stream might differ.
    
    if content:
        await websocket.send_json({
            "type": "chunk",
            "content": content
        })

if __name__ == "__main__":
    uvicorn.run("web_main:app", host="0.0.0.0", port=8000, reload=True)
