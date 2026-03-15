FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    wget \
    xvfb \
    libgl1-mesa-glx \
    libxi6 \
    libxrender1 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# Install Blender (headless)
RUN wget -q https://mirror.clarkson.edu/blender/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz \
    && tar -xf blender-4.2.0-linux-x64.tar.xz \
    && mv blender-4.2.0-linux-x64 /opt/blender \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && rm blender-4.2.0-linux-x64.tar.xz

WORKDIR /app
COPY . /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -e ".[telegram]"

# Copy addon to Blender's addon directory
RUN mkdir -p /root/.config/blender/4.2/scripts/addons/blenderbot_addon \
    && cp -r blender_addon/* /root/.config/blender/4.2/scripts/addons/blenderbot_addon/

# Startup script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 9876

CMD ["/app/docker-entrypoint.sh"]
