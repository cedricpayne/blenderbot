"""Telegram bot interface for BlenderBot.

Users can send text, images, or videos via Telegram and receive rendered 3D scenes back.
The bot can connect to a remote Blender instance or run Blender headlessly.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from .bot import BlenderBot

logger = logging.getLogger("blenderbot.telegram")


class TelegramBlenderBot:
    """Telegram bot that interfaces with BlenderBot."""

    def __init__(
        self,
        telegram_token: str,
        anthropic_api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        blender_host: str = "127.0.0.1",
        blender_port: int = 9876,
        mode: str = "tools",
        render_by_default: bool = True,
    ):
        self.telegram_token = telegram_token
        self.render_by_default = render_by_default
        self.bot = BlenderBot(
            api_key=anthropic_api_key,
            model=model,
            blender_host=blender_host,
            blender_port=blender_port,
            mode=mode,
        )
        self._user_sessions: dict[int, BlenderBot] = {}

    def _get_bot(self, user_id: int) -> BlenderBot:
        """Get or create a per-user BlenderBot instance (separate conversation history)."""
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = BlenderBot(
                api_key=self.bot.claude.client.api_key,
                model=self.bot.claude.model,
                blender_host=self.bot.blender.host,
                blender_port=self.bot.blender.port,
                mode=self.bot.mode,
            )
        return self._user_sessions[user_id]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Welcome to BlenderBot!\n\n"
            "Send me a text description and I'll create a 3D scene in Blender.\n\n"
            "Commands:\n"
            "/start - Show this message\n"
            "/status - Check Blender connection\n"
            "/clear - Clear the Blender scene\n"
            "/history - Clear conversation history\n"
            "/render - Render current scene\n"
            "/mode [tools|script] - Switch generation mode\n\n"
            "You can also send:\n"
            "- Text: describe a 3D scene\n"
            "- Image: I'll recreate it in 3D\n"
            "- Video: I'll create an animation from it"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot = self._get_bot(update.effective_user.id)
        if bot.is_blender_connected():
            await update.message.reply_text("Blender is connected and ready!")
        else:
            await update.message.reply_text(
                "Cannot reach Blender. Make sure:\n"
                "1. Blender is running with the BlenderBot addon\n"
                "2. The server is started in the addon panel"
            )

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot = self._get_bot(update.effective_user.id)
        result = bot.clear_scene()
        if result.ok:
            await update.message.reply_text("Scene cleared!")
        else:
            await update.message.reply_text(f"Error: {result.error}")

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot = self._get_bot(update.effective_user.id)
        bot.clear_history()
        await update.message.reply_text("Conversation history cleared.")

    async def render_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot = self._get_bot(update.effective_user.id)
        await update.message.reply_text("Rendering scene...")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = f.name

        try:
            result = bot.blender.render(output_path=output_path, samples=64)
            if result.ok and Path(output_path).exists():
                await update.message.reply_photo(
                    photo=open(output_path, "rb"),
                    caption="Render complete!",
                )
            else:
                await update.message.reply_text(f"Render failed: {result.error}")
        finally:
            if Path(output_path).exists():
                os.unlink(output_path)

    async def mode_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot = self._get_bot(update.effective_user.id)
        args = context.args
        if args and args[0] in ("tools", "script"):
            bot.mode = args[0]
            bot.claude.mode = args[0]
            await update.message.reply_text(f"Switched to {args[0]} mode.")
        else:
            await update.message.reply_text(
                f"Current mode: {bot.mode}\n"
                "Usage: /mode tools  or  /mode script"
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages - generate 3D scene from description."""
        bot = self._get_bot(update.effective_user.id)
        prompt = update.message.text

        await update.message.reply_text(f"Creating 3D scene: {prompt[:100]}...")

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                output_path = f.name

            result = bot.text_to_render(
                prompt=prompt,
                render=self.render_by_default,
                output_path=output_path,
                engine="CYCLES",
                samples=64,
            )

            response_text = _format_result(result)

            if self.render_by_default and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                await update.message.reply_photo(
                    photo=open(output_path, "rb"),
                    caption=response_text[:1024],
                )
            else:
                await update.message.reply_text(response_text)

        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        finally:
            if Path(output_path).exists():
                os.unlink(output_path)

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image messages - recreate image as 3D scene."""
        bot = self._get_bot(update.effective_user.id)

        photo = update.message.photo[-1]  # Highest resolution
        caption = update.message.caption or ""

        await update.message.reply_text("Analyzing image and creating 3D scene...")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_file:
            file = await context.bot.get_file(photo.file_id)
            await file.download_to_drive(img_file.name)
            image_path = img_file.name

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                output_path = f.name

            result = bot.image_to_render(
                image_path=image_path,
                prompt=caption,
                render=self.render_by_default,
                output_path=output_path,
                engine="CYCLES",
                samples=64,
            )

            response_text = _format_result(result)

            if self.render_by_default and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                await update.message.reply_photo(
                    photo=open(output_path, "rb"),
                    caption=response_text[:1024],
                )
            else:
                await update.message.reply_text(response_text)

        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        finally:
            for p in (image_path, output_path):
                if Path(p).exists():
                    os.unlink(p)

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video messages - create 3D animation from video."""
        bot = self._get_bot(update.effective_user.id)

        video = update.message.video or update.message.animation
        if not video:
            await update.message.reply_text("Could not process video.")
            return

        caption = update.message.caption or ""
        await update.message.reply_text("Analyzing video and creating 3D animation...")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vid_file:
            file = await context.bot.get_file(video.file_id)
            await file.download_to_drive(vid_file.name)
            video_path = vid_file.name

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                output_path = f.name

            result = bot.video_to_render(
                video_path=video_path,
                prompt=caption,
                render=False,  # Animation rendering takes too long for telegram
            )

            response_text = _format_result(result)
            await update.message.reply_text(response_text)

        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
        finally:
            if Path(video_path).exists():
                os.unlink(video_path)

    def run(self):
        """Start the Telegram bot (blocking)."""
        app = Application.builder().token(self.telegram_token).build()

        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("clear", self.clear_command))
        app.add_handler(CommandHandler("history", self.history_command))
        app.add_handler(CommandHandler("render", self.render_command))
        app.add_handler(CommandHandler("mode", self.mode_command))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_image))
        app.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION, self.handle_video))

        logger.info("Starting Telegram bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def _format_result(result: dict) -> str:
    """Format a BlenderBot result for Telegram."""
    parts = []

    if "tool_calls" in result:
        calls = result["tool_calls"]
        success = sum(1 for tc in calls if tc["status"] == "ok")
        parts.append(f"Executed {success}/{len(calls)} tools successfully.")
        for tc in calls:
            status = "OK" if tc["status"] == "ok" else "FAIL"
            parts.append(f"  [{status}] {tc['tool']}")
            if tc.get("error"):
                parts.append(f"    Error: {tc['error']}")

    elif "execution" in result:
        exec_info = result["execution"]
        if exec_info["status"] == "ok":
            parts.append(f"Scene created: {exec_info.get('result', 'Success')}")
        else:
            parts.append(f"Error: {exec_info.get('error', 'Unknown')}")

    if "render" in result:
        render_info = result["render"]
        if render_info["status"] == "ok":
            parts.append("Render complete!")
        else:
            parts.append(f"Render error: {render_info.get('error')}")

    return "\n".join(parts) or "Done."


def main():
    """Entry point for running the Telegram bot."""
    import argparse

    parser = argparse.ArgumentParser(description="BlenderBot Telegram Bot")
    parser.add_argument("--telegram-token", default=os.environ.get("TELEGRAM_BOT_TOKEN"))
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--model", default=os.environ.get("BLENDERBOT_MODEL", "claude-sonnet-4-20250514"))
    parser.add_argument("--blender-host", default=os.environ.get("BLENDER_HOST", "127.0.0.1"))
    parser.add_argument("--blender-port", type=int, default=int(os.environ.get("BLENDER_PORT", "9876")))
    parser.add_argument("--mode", default=os.environ.get("BLENDERBOT_MODE", "tools"), choices=["tools", "script"])
    parser.add_argument("--no-render", action="store_true", help="Don't render by default")

    args = parser.parse_args()

    if not args.telegram_token:
        print("Error: Set TELEGRAM_BOT_TOKEN environment variable or use --telegram-token")
        exit(1)

    logging.basicConfig(level=logging.INFO)

    tg_bot = TelegramBlenderBot(
        telegram_token=args.telegram_token,
        anthropic_api_key=args.anthropic_key,
        model=args.model,
        blender_host=args.blender_host,
        blender_port=args.blender_port,
        mode=args.mode,
        render_by_default=not args.no_render,
    )
    tg_bot.run()


if __name__ == "__main__":
    main()
