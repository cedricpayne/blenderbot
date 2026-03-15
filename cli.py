#!/usr/bin/env python3
"""BlenderBot CLI - Interactive AI-powered 3D content generation."""

import argparse
import json
import os
import sys

from blenderbot.bot import BlenderBot


def main():
    parser = argparse.ArgumentParser(
        description="BlenderBot - AI-powered 3D content generation with Claude and Blender",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Blender addon host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9876, help="Blender addon port (default: 9876)")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Claude model to use")
    parser.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Ping
    subparsers.add_parser("ping", help="Check if Blender is connected")

    # Text to render
    text_parser = subparsers.add_parser("text", help="Generate 3D scene from text")
    text_parser.add_argument("prompt", help="Text description of the 3D scene")
    text_parser.add_argument("--render", action="store_true", help="Render after creating")
    text_parser.add_argument("--output", default="/tmp/blenderbot_render.png", help="Render output path")
    text_parser.add_argument("--engine", default="CYCLES", choices=["CYCLES", "BLENDER_EEVEE_NEXT"])
    text_parser.add_argument("--samples", type=int, default=128)

    # Image to render
    image_parser = subparsers.add_parser("image", help="Generate 3D scene from image")
    image_parser.add_argument("image_path", help="Path to reference image")
    image_parser.add_argument("--prompt", default="", help="Additional instructions")
    image_parser.add_argument("--render", action="store_true", help="Render after creating")
    image_parser.add_argument("--output", default="/tmp/blenderbot_render.png")
    image_parser.add_argument("--engine", default="CYCLES", choices=["CYCLES", "BLENDER_EEVEE_NEXT"])
    image_parser.add_argument("--samples", type=int, default=128)

    # Video to render
    video_parser = subparsers.add_parser("video", help="Generate 3D animation from video")
    video_parser.add_argument("video_path", help="Path to reference video")
    video_parser.add_argument("--prompt", default="", help="Additional instructions")
    video_parser.add_argument("--render", action="store_true", help="Render after creating")
    video_parser.add_argument("--output", default="/tmp/blenderbot_anim_")
    video_parser.add_argument("--engine", default="CYCLES", choices=["CYCLES", "BLENDER_EEVEE_NEXT"])
    video_parser.add_argument("--samples", type=int, default=64)
    video_parser.add_argument("--frame-start", type=int, default=1)
    video_parser.add_argument("--frame-end", type=int, default=250)

    # Interactive mode
    subparsers.add_parser("interactive", help="Start interactive session")

    # Clear scene
    subparsers.add_parser("clear", help="Clear the Blender scene")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    bot = BlenderBot(
        api_key=args.api_key,
        model=args.model,
        blender_host=args.host,
        blender_port=args.port,
    )

    if args.command == "ping":
        if bot.is_blender_connected():
            print("Blender is connected and ready!")
        else:
            print("Cannot reach Blender. Make sure:")
            print("  1. Blender is running")
            print("  2. The BlenderBot addon is installed and enabled")
            print("  3. The server is started (Sidebar > BlenderBot > Start)")
            sys.exit(1)

    elif args.command == "text":
        print(f"Generating 3D scene: {args.prompt}")
        result = bot.text_to_render(
            prompt=args.prompt,
            render=args.render,
            output_path=args.output,
            engine=args.engine,
            samples=args.samples,
        )
        _print_result(result)

    elif args.command == "image":
        print(f"Generating 3D scene from image: {args.image_path}")
        result = bot.image_to_render(
            image_path=args.image_path,
            prompt=args.prompt,
            render=args.render,
            output_path=args.output,
            engine=args.engine,
            samples=args.samples,
        )
        _print_result(result)

    elif args.command == "video":
        print(f"Generating 3D animation from video: {args.video_path}")
        result = bot.video_to_render(
            video_path=args.video_path,
            prompt=args.prompt,
            render=args.render,
            output_path=args.output,
            animation=True,
            engine=args.engine,
            samples=args.samples,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
        )
        _print_result(result)

    elif args.command == "clear":
        result = bot.clear_scene()
        if result.ok:
            print("Scene cleared.")
        else:
            print(f"Error: {result.error}")

    elif args.command == "interactive":
        _interactive_mode(bot)


def _interactive_mode(bot: BlenderBot):
    """Run an interactive session."""
    print("BlenderBot Interactive Mode")
    print("=" * 40)
    print("Commands:")
    print("  /text <prompt>     - Generate from text")
    print("  /image <path>      - Generate from image")
    print("  /video <path>      - Generate from video")
    print("  /render [path]     - Render current scene")
    print("  /clear             - Clear the scene")
    print("  /history clear     - Clear conversation history")
    print("  /quit              - Exit")
    print()

    if not bot.is_blender_connected():
        print("WARNING: Blender is not connected. Start the addon first.")
        print()

    while True:
        try:
            user_input = input("blenderbot> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("Goodbye!")
            break
        elif user_input == "/clear":
            result = bot.clear_scene()
            print("Scene cleared." if result.ok else f"Error: {result.error}")
        elif user_input == "/history clear":
            bot.clear_history()
            print("Conversation history cleared.")
        elif user_input.startswith("/render"):
            parts = user_input.split(maxsplit=1)
            output = parts[1] if len(parts) > 1 else "/tmp/blenderbot_render.png"
            print(f"Rendering to {output}...")
            result = bot.blender.render(output_path=output)
            if result.ok:
                print(f"Render saved to {output}")
            else:
                print(f"Render error: {result.error}")
        elif user_input.startswith("/image "):
            path = user_input[7:].strip()
            prompt = input("Additional instructions (or Enter to skip): ").strip()
            print("Generating 3D scene from image...")
            result = bot.image_to_render(image_path=path, prompt=prompt)
            _print_result(result)
        elif user_input.startswith("/video "):
            path = user_input[7:].strip()
            prompt = input("Additional instructions (or Enter to skip): ").strip()
            print("Generating 3D animation from video...")
            result = bot.video_to_render(video_path=path, prompt=prompt)
            _print_result(result)
        elif user_input.startswith("/text "):
            prompt = user_input[6:].strip()
            print("Generating 3D scene...")
            result = bot.text_to_render(prompt=prompt)
            _print_result(result)
        elif user_input.startswith("/"):
            print(f"Unknown command: {user_input.split()[0]}")
        else:
            # Default: treat as text prompt
            print("Generating 3D scene...")
            result = bot.text_to_render(prompt=user_input)
            _print_result(result)


def _print_result(result: dict):
    """Print the result of a generation."""
    exec_info = result.get("execution", {})
    if exec_info.get("status") == "ok":
        print(f"Success: {exec_info.get('result', 'Scene created')}")
    else:
        print(f"Execution error: {exec_info.get('error', 'Unknown error')}")
        return

    render_info = result.get("render")
    if render_info:
        if render_info.get("status") == "ok":
            print(f"Rendered to: {render_info['output']}")
        else:
            print(f"Render error: {render_info.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
