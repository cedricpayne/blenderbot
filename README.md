# BlenderBot

AI-powered 3D content generation using Claude and Blender. Describe what you want in natural language (or provide an image/video reference) and BlenderBot generates and executes Blender Python scripts to create 3D scenes, animations, and sculptures.

## Features

- **Text to 3D** — Describe a scene in natural language, get a 3D scene in Blender
- **Image to 3D** — Provide a reference image, get a 3D recreation
- **Video to 3D Animation** — Provide a reference video, get a keyframed animation
- **Interactive mode** — Iteratively build scenes with conversational context
- **Render output** — Automatically render results to images or animation frames

## Architecture

```
User Input (text/image/video)
        │
        ▼
   Claude API ──────► Blender Python Script
        │
        ▼
   BlenderBot Client ──(socket)──► Blender Addon Server
                                        │
                                        ▼
                                  Execute bpy script
                                        │
                                        ▼
                                   3D Scene / Render
```

## Setup

### 1. Install Python dependencies

```bash
pip install -e .
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### 3. Install the Blender addon

1. Open Blender (4.0+)
2. Edit → Preferences → Add-ons → Install
3. Select the `blender_addon/` folder
4. Enable "BlenderBot Remote"

### 4. Start the addon server

In Blender's 3D Viewport sidebar (press N), find the "BlenderBot" tab and click **Start BlenderBot Server**.

## Usage

### CLI

```bash
# Check connection
python cli.py ping

# Text to 3D
python cli.py text "Create a futuristic city with neon lights"

# Text to 3D with render
python cli.py text "A marble sculpture of a hand" --render --output sculpture.png

# Image to 3D
python cli.py image reference.jpg --prompt "Make it low-poly style"

# Video to animation
python cli.py video dance.mp4 --render --frame-end 120

# Interactive mode
python cli.py interactive

# Clear scene
python cli.py clear
```

### Python API

```python
from blenderbot.bot import BlenderBot

bot = BlenderBot()

# Text to 3D
result = bot.text_to_render("Create a crystal cave with glowing minerals")

# Image reference
result = bot.image_to_render("photo.jpg", prompt="Stylize as cartoon")

# Video reference
result = bot.video_to_render("clip.mp4", render=True)

# Iterative building (conversation history preserved)
bot.text_to_render("Create a chess board")
bot.text_to_render("Add all the pieces in starting position")
bot.text_to_render("Make the black pieces obsidian and white pieces marble")
```

### Interactive Mode

```
blenderbot> a dragon perched on a mountain
Success: Created dragon scene with mountain base

blenderbot> make the dragon breathe fire
Success: Added particle-based fire breath

blenderbot> /render dragon_scene.png
Rendered to: dragon_scene.png
```

## Requirements

- Python 3.10+
- Blender 4.0+
- Anthropic API key
- ffmpeg (for video-to-3D feature)
