"""Basic usage examples for BlenderBot."""

from blenderbot.bot import BlenderBot

# ---- Tools mode (default) ----
# Claude calls structured tools like create_object, set_material, etc.
bot = BlenderBot(mode="tools")

if not bot.is_blender_connected():
    print("Start Blender and enable the BlenderBot addon first!")
    exit(1)

# Text to 3D - Claude decides which tools to call
result = bot.text_to_render("Create a low-poly mountain landscape with pine trees")
print(f"Tool calls: {len(result.get('tool_calls', []))}")

# Direct tool calls - bypass Claude
bot.call_tool("create_object", entity_type="SPHERE", name="Sun", location=[5, 5, 10], scale=[2, 2, 2])
bot.call_tool("set_material", object_name="Sun", color=[1.0, 0.9, 0.3], emission_color=[1.0, 0.9, 0.3], emission_strength=5.0)

# Image reference
result = bot.image_to_render("reference.jpg", prompt="Recreate as stylized 3D")

# Iterative building with conversation history
bot.text_to_render("Create a wooden table")
bot.text_to_render("Add a vase with flowers on the table")
bot.text_to_render("Add dramatic side lighting")

# ---- Script mode ----
# Claude generates raw Blender Python code for maximum flexibility
bot_script = BlenderBot(mode="script")
result = bot_script.text_to_render(
    "Create a procedural crystal cave with glowing minerals",
    render=True,
    output_path="/tmp/crystal_cave.png",
    samples=64,
)
