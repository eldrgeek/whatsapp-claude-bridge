"""
WhatsApp-Claude Code Bridge
============================
Routes WhatsApp messages to a persistent Claude Code subprocess.
"""

import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .config import settings
from .whatsapp_handler import WhatsAppHandler
from .claude_code_subprocess import get_claude_code, shutdown_claude_code


app = FastAPI(title="WhatsApp-Claude Code Bridge")


@app.on_event("shutdown")
async def _shutdown_event():
    """Clean up Claude Code subprocess on exit."""
    await shutdown_claude_code()


whatsapp = WhatsAppHandler()
_busy: dict[str, bool] = {}


@app.get("/")
async def health():
    return {"status": "running", "service": "WhatsApp-Claude Code Bridge"}


@app.get("/webhook")
async def webhook_verify():
    return {"status": "ok", "message": "Webhook endpoint ready"}


@app.post("/webhook")
async def webhook(request: Request):
    form = await request.form()
    
    print("[WEBHOOK] Incoming request", flush=True)
    
    from_raw = form.get("From", "")
    body = (form.get("Body") or "").strip()
    status = form.get("MessageStatus")
    
    # Ignore status-only callbacks
    if status and not body:
        return JSONResponse({"status": "ok"})
    
    from_number = from_raw.replace("whatsapp:", "")
    
    # Security: only authorized number
    if from_number != settings.approved_phone_number:
        print(f"[REJECT] {from_number} not authorized", flush=True)
        return JSONResponse({"status": "unauthorized"})
    
    print(f"[MSG] {from_number}: {body[:80]}", flush=True)
    
    # Special commands
    if body.upper() == "/RESET":
        # Could restart subprocess here
        whatsapp.send_message(from_number, "Session reset requested.")
        return JSONResponse({"status": "ok"})
    
    # Process in background
    task = asyncio.ensure_future(_process(from_number, body))
    task.add_done_callback(_task_done)
    
    return JSONResponse({"status": "ok"})


def _task_done(task: asyncio.Task) -> None:
    try:
        exc = task.exception()
        if exc:
            import traceback
            print(f"[TASK ERROR] {exc}", flush=True)
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    except asyncio.CancelledError:
        pass


async def _process(from_number: str, text: str) -> None:
    """Send message to Claude Code and relay response to WhatsApp."""
    
    # Guard against concurrent processing
    if from_number in _busy:
        whatsapp.send_message(from_number, "Please wait for the previous request to finish...")
        return
    
    _busy[from_number] = True
    
    try:
        claude_code = get_claude_code()
        
        # Send to Claude Code subprocess
        response = await claude_code.send_message(text)
        
        if response:
            # WhatsApp has a ~1600 char limit, split if needed
            if len(response) > 1500:
                chunks = _split_response(response, 1500)
                for chunk in chunks:
                    whatsapp.send_message(from_number, chunk)
                    await asyncio.sleep(0.5)  # Rate limit
            else:
                whatsapp.send_message(from_number, response)
        else:
            whatsapp.send_message(from_number, "[No response from Claude Code]")
            
    except Exception as exc:
        print(f"[ERROR] {exc}", flush=True)
        whatsapp.send_message(from_number, f"Error: {exc}")
    finally:
        _busy.pop(from_number, None)


def _split_response(text: str, max_len: int) -> list[str]:
    """Split response into chunks, preferring paragraph breaks."""
    chunks = []
    current = ""
    
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_len:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            # If single paragraph is too long, split by sentences
            if len(para) > max_len:
                sentences = para.replace(". ", ".\n").split("\n")
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= max_len:
                        current += (" " if current else "") + sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para
    
    if current:
        chunks.append(current)
    
    return chunks


def main():
    import uvicorn
    
    print("WhatsApp-Claude Code Bridge")
    print(f"  Phone : {settings.approved_phone_number}")
    print(f"  Server: http://{settings.server_host}:{settings.server_port}")
    print()
    print("Messages route to a persistent Claude Code subprocess.")
    print()
    
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
