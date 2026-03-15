"""Basic usage examples for BlenderBot."""

from blenderbot.bot import BlenderBot

# Initialize the bot (set ANTHROPIC_API_KEY env var or pass api_key)
bot = BlenderBot()

# Check connection
if not bot.is_blender_connected():
    print("Start Blender and enable the BlenderBot addon first!")
    exit(1)

# --- Text to 3D ---
result = bot.text_to_render(
    prompt="Create a low-poly mountain landscape with pine trees and a lake",
    render=True,
    output_path="/tmp/landscape.png",
    engine="CYCLES",
    samples=64,
)
print(f"Text result: {result['execution']}")

# --- Image to 3D ---
result = bot.image_to_render(
    image_path="reference.jpg",
    prompt="Recreate this as a stylized 3D scene",
    render=True,
    output_path="/tmp/from_image.png",
)
print(f"Image result: {result['execution']}")

# --- Video to 3D Animation ---
result = bot.video_to_render(
    video_path="animation_ref.mp4",
    prompt="Create a bouncing ball animation matching this reference",
    render=True,
    output_path="/tmp/anim_",
    frame_end=120,
)
print(f"Video result: {result['execution']}")

# --- Interactive conversation (history is preserved) ---
bot.text_to_render("Create a wooden table")
bot.text_to_render("Add a vase with flowers on top of the table")
bot.text_to_render("Add dramatic lighting from the left side")
