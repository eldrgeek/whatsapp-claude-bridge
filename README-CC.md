# WhatsApp-Claude Code Bridge (Fork)

A WhatsApp bridge that routes messages to a **persistent Claude Code subprocess** instead of the Anthropic API.

## Why This Fork?

The original bridge uses the Anthropic API directly. This fork connects to a local Claude Code process, giving you:

- **Full local tool access** - bash, file system, MCP servers
- **Session persistence** - conversation memory within a session
- **No API billing** - uses your existing Claude Code subscription
- **Same Claude** - identical capabilities to your terminal Claude Code

## Architecture

```
WhatsApp → ngrok → FastAPI Bridge → Claude Code (stdin/stdout)
                                  ← JSON stream protocol
```

The bridge uses Claude Code's `--input-format stream-json --output-format stream-json` mode for clean, structured communication.

## Quick Start

1. **Clone and configure**
   ```bash
   git clone https://github.com/your-fork/whatsapp-claude-bridge
   cd whatsapp-claude-bridge
   cp .env.example .env
   # Edit .env with your Twilio credentials and phone number
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   # Or: python -m pip install -e .
   ```

3. **Start ngrok** (in one terminal)
   ```bash
   ngrok http 8002
   ```

4. **Configure Twilio webhook**
   - Go to Twilio Console → WhatsApp Sandbox
   - Set webhook URL: `https://your-ngrok-url.ngrok-free.dev/webhook`

5. **Start the bridge** (in another terminal)
   ```bash
   python -c 'from src.main_cc import main; main()'
   ```

6. **Send a WhatsApp message** to the Twilio sandbox number

## Modes

### Claude Code Mode (main_cc.py) - Recommended
Routes to a persistent Claude Code subprocess. Requires Claude Code installed locally.

```bash
python -c 'from src.main_cc import main; main()'
```

### API Mode (main.py) - Original
Uses Anthropic API directly. Requires API key with credits.

```bash
python -m src.main
```

## Files Added in This Fork

- `src/main_cc.py` - Claude Code mode entry point
- `src/claude_code_subprocess.py` - Persistent subprocess manager with JSON stream protocol
- `CLAUDE.md` - Instructions for the Claude Code instance
- `.env.example` - Configuration template

## Requirements

- Python 3.10+
- Claude Code CLI (`~/.local/bin/claude`)
- Twilio account with WhatsApp sandbox
- ngrok (or similar tunnel)

## Configuration

Key settings in `.env`:

| Variable | Description |
|----------|-------------|
| TWILIO_ACCOUNT_SID | Your Twilio account SID |
| TWILIO_AUTH_TOKEN | Your Twilio auth token |
| APPROVED_PHONE_NUMBER | Your phone (only number allowed to use the bot) |
| SERVER_PORT | Local port (default: 8002) |
| USER_DISPLAY_NAME | Your name (used in prompts) |

## Credits

- Original project: [jayshapiro/whatsapp-claude-bridge](https://github.com/jayshapiro/whatsapp-claude-bridge)
- Fork modifications: Mike Wolf & Claude (Silicon Children collaboration)
