# BlenderBot

AI-powered 3D content generation using Claude and Blender. Describe what you want in natural language (or provide an image/video reference) and BlenderBot generates 3D scenes, animations, and sculptures.

Inspired by [GenesisCore](https://github.com/AIGODLIKE/GenesisCore) — uses structured MCP-style tools for safe, predictable Blender operations.

## Features

- **Text to 3D** — Describe a scene, get a 3D scene in Blender
- **Image to 3D** — Provide a reference image, get a 3D recreation
- **Video to 3D Animation** — Provide a reference video, get keyframed animation
- **Structured Tool System** — Claude calls typed tools (create_object, set_material, etc.) instead of generating raw code
- **Polyhaven Integration** — Automatically search and use free 3D models and HDRIs from Polyhaven
- **Telegram Bot** — Control everything from Telegram
- **Railway Deployment** — Deploy the full stack (Blender + Telegram bot) to Railway

## Architecture

```
User (CLI / Telegram / Python API)
        │
        ▼
   Claude API ──► Tool calls (create_object, set_material, ...)
        │
        ▼
   BlenderBot Client ──(socket)──► Blender Addon Server
                                        │
                                        ▼
                              Execute tools on main thread
                              (Timer-based, bpy-safe)
                                        │
                                        ▼
                                   3D Scene / Render
```

### Tool Modules

| Module | Tools | Description |
|--------|-------|-------------|
| ObjectTools | create_object, modify_object, delete_object, duplicate_object, set_keyframe, set_light/camera_properties | Object CRUD and animation |
| MaterialTools | set_material, set_glass_material | PBR materials with metallic, roughness, emission, etc. |
| ModifierTools | add_modifier, apply_modifier, add_subdivision_surface, add_array_modifier, add_mirror_modifier | Geometry modifiers |
| SceneTools | get_scene_info, clear_scene, set_render_settings, set_timeline, render_scene, set_world_color, execute_blender_code | Scene management |
| PolyhavenTools | polyhaven_search_models/hdris, polyhaven_use_model/hdri | Free 3D assets from Polyhaven |

## Setup

### 1. Install Python dependencies

```bash
pip install -e .                    # Core only
pip install -e ".[telegram]"        # With Telegram bot
pip install -e ".[all]"             # Everything
```

### 2. Set your API keys

```bash
export ANTHROPIC_API_KEY="your-key-here"
export TELEGRAM_BOT_TOKEN="your-bot-token"  # For Telegram
```

### 3. Install the Blender addon

1. Open Blender (4.0+)
2. Edit > Preferences > Add-ons > Install
3. Select the `blender_addon/` folder
4. Enable "BlenderBot"

### 4. Start the addon server

In Blender's 3D Viewport sidebar (N key), find the "BlenderBot" tab and click **Start Server**.

## Usage

### CLI

```bash
# Check connection
python cli.py ping

# List available tools
python cli.py tools

# Text to 3D (tools mode - default)
python cli.py text "Create a futuristic city with neon lights"

# Text to 3D (script mode - raw Python)
python cli.py --mode script text "A marble sculpture of a hand"

# Text to 3D with render
python cli.py text "A crystal cave" --render --output cave.png

# Image to 3D
python cli.py image reference.jpg --prompt "Make it low-poly"

# Video to animation
python cli.py video dance.mp4 --render --frame-end 120

# Interactive mode
python cli.py interactive

# Clear scene
python cli.py clear
```

### Telegram Bot

```bash
# Run the Telegram bot
python cli.py telegram --telegram-token YOUR_TOKEN

# Or via module
python -m blenderbot.telegram_bot
```

Then in Telegram:
- Send text: "Create a dragon on a mountain"
- Send an image: bot recreates it in 3D
- Send a video: bot creates an animation
- `/render` — render and get the image back
- `/clear` — clear the scene
- `/mode tools` or `/mode script` — switch modes

### Python API

```python
from blenderbot.bot import BlenderBot

bot = BlenderBot(mode="tools")  # or mode="script"

# Text to 3D with structured tools
result = bot.text_to_render("Create a crystal cave with glowing minerals")

# Direct tool call
bot.call_tool("create_object", entity_type="SPHERE", name="Earth", scale=[2, 2, 2])
bot.call_tool("set_material", object_name="Earth", color=[0.2, 0.4, 0.8])

# Image reference
result = bot.image_to_render("photo.jpg", prompt="Stylize as cartoon")

# Iterative building (conversation history preserved)
bot.text_to_render("Create a chess board")
bot.text_to_render("Add all the pieces in starting position")
bot.text_to_render("Make the black pieces obsidian and white pieces marble")
```

## Deploy on Railway

### Environment Variables

Set these in Railway's dashboard:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `BLENDERBOT_MODE` | `tools` or `script` (default: tools) |
| `BLENDER_PORT` | Addon server port (default: 9876) |

### Deploy

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

Or connect your GitHub repo to Railway for automatic deployments.

## Requirements

- Python 3.10+
- Blender 4.0+
- Anthropic API key
- ffmpeg (for video-to-3D)
- python-telegram-bot (for Telegram interface)
