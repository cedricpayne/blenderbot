#!/bin/bash
set -e

echo "Starting BlenderBot..."

# Start Blender in background with the addon auto-started
# Use Xvfb for headless rendering
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Start Blender in background mode with the addon
blender --background --python-expr "
import bpy
import sys

# Enable the addon
bpy.ops.preferences.addon_enable(module='blenderbot_addon')

# Start the server
bpy.ops.blenderbot.start_server()

# Keep Blender running
print('[BlenderBot] Blender started with addon server')
import time
while True:
    time.sleep(1)
" &

BLENDER_PID=$!
echo "Blender started (PID: $BLENDER_PID)"

# Wait for Blender server to be ready
echo "Waiting for Blender addon server..."
for i in {1..30}; do
    if python3 -c "
import socket
s = socket.socket()
try:
    s.connect(('127.0.0.1', ${BLENDER_PORT:-9876}))
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
        echo "Blender server is ready!"
        break
    fi
    sleep 1
done

# Start the Telegram bot
echo "Starting Telegram bot..."
exec python3 -m blenderbot.telegram_bot \
    --blender-host 127.0.0.1 \
    --blender-port "${BLENDER_PORT:-9876}" \
    --mode "${BLENDERBOT_MODE:-tools}"
