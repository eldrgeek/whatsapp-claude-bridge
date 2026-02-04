"""
Claude Code Persistent Subprocess
=================================
Maintains a long-running Claude Code process using stream-json protocol.
Messages go via stdin as JSON, responses come via stdout as JSON lines.
Session context is maintained across messages.
"""

import asyncio
import subprocess
import os
import json
from pathlib import Path
from typing import Optional
from .config import settings


class ClaudeCodePersistent:
    """Manages a persistent Claude Code subprocess with stream-json protocol."""

    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path(__file__).parent.parent  # whatsapp-claude-bridge/
        self.claude_path = self._find_claude()
        self.process: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()
        self._initialized = False
        
        if not self.claude_path:
            raise RuntimeError("Could not find 'claude' executable")
        
        print(f"[CC] Claude Code at: {self.claude_path}", flush=True)
        print(f"[CC] Working dir: {self.working_dir}", flush=True)

    def _find_claude(self) -> Optional[str]:
        import shutil
        claude = shutil.which("claude")
        if claude:
            return claude
        for path in [
            str(Path.home() / ".local/bin/claude"),
            "/usr/local/bin/claude",
            "/opt/homebrew/bin/claude",
        ]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    async def ensure_running(self) -> None:
        """Start Claude Code subprocess if not already running."""
        if self.process is not None and self.process.returncode is None:
            return
        
        print("[CC] Starting persistent Claude Code subprocess...", flush=True)
        
        env = os.environ.copy()
        env["TERM"] = "dumb"
        
        self.process = await asyncio.create_subprocess_exec(
            self.claude_path,
            "--print",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(self.working_dir),
        )
        
        self._initialized = False
        print(f"[CC] Subprocess started, PID: {self.process.pid}", flush=True)

    async def send_message(self, message: str) -> str:
        """Send a message and wait for the complete response.
        
        Args:
            message: User's message text
            
        Returns:
            Claude's response text
        """
        async with self._lock:
            await self.ensure_running()
            
            # Format message as JSON
            msg_json = json.dumps({
                "type": "user",
                "message": {
                    "role": "user",
                    "content": message
                }
            })
            
            print(f"[CC] Sending: {message[:60]}...", flush=True)
            
            try:
                # Write message to stdin
                self.process.stdin.write((msg_json + "\n").encode())
                await self.process.stdin.drain()
                
                # Read responses until we get a result
                result_text = ""
                while True:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=120
                    )
                    
                    if not line:
                        print("[CC] EOF from subprocess", flush=True)
                        self.process = None
                        break
                    
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    
                    try:
                        data = json.loads(line_str)
                    except json.JSONDecodeError:
                        print(f"[CC] Non-JSON line: {line_str[:100]}", flush=True)
                        continue
                    
                    msg_type = data.get("type")
                    
                    if msg_type == "system":
                        subtype = data.get("subtype")
                        if subtype == "init" and not self._initialized:
                            print(f"[CC] Session: {data.get('session_id', 'unknown')}", flush=True)
                            self._initialized = True
                    
                    elif msg_type == "assistant":
                        # Could stream these chunks to WhatsApp eventually
                        pass
                    
                    elif msg_type == "result":
                        result_text = data.get("result", "")
                        cost = data.get("total_cost_usd", 0)
                        duration = data.get("duration_ms", 0)
                        print(f"[CC] Done: {duration}ms, ${cost:.4f}", flush=True)
                        break
                
                print(f"[CC] Response ({len(result_text)} chars)", flush=True)
                return result_text
                
            except asyncio.TimeoutError:
                print("[CC] Timeout", flush=True)
                return "Request timed out. Please try again."
            except Exception as e:
                print(f"[CC] Error: {e}", flush=True)
                self.process = None
                raise

    async def shutdown(self) -> None:
        """Gracefully shut down the subprocess."""
        if self.process and self.process.returncode is None:
            print("[CC] Shutting down...", flush=True)
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except:
                self.process.kill()
            self.process = None


# Global instance
_instance: Optional[ClaudeCodePersistent] = None


def get_claude_code() -> ClaudeCodePersistent:
    global _instance
    if _instance is None:
        _instance = ClaudeCodePersistent()
    return _instance


async def shutdown_claude_code() -> None:
    global _instance
    if _instance:
        await _instance.shutdown()
        _instance = None
