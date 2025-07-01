#!/bin/bash

# Check if Python 3 is available
if ! command -v python3 &>/dev/null; then
  echo "Python 3 is not installed. Installing..."
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip
fi

# Ensure pip is installed
if ! command -v pip3 &>/dev/null; then
  echo "pip3 not found. Installing..."
  sudo apt install -y python3-pip
fi

# Required system dependencies
echo "Installing system dependencies for headless Chromium and Flask rendering..."
sudo apt install -y \
  build-essential \
  libglib2.0-0 \
  libnss3 \
  libgconf-2-4 \
  libfontconfig1 \
  libxss1 \
  libasound2 \
  libxtst6 \
  libxrandr2 \
  xdg-utils \
  wget \
  unzip \
  curl \
  fonts-liberation \
  libappindicator3-1 \
  lsb-release \
  libu2f-udev \
  libatk-bridge2.0-0 \
  libgtk-3-0

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
if [ -f "requirements.txt" ]; then
  echo "Installing dependencies from requirements.txt..."
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "requirements.txt not found!"
  exit 1
fi

# Download Chromium (needed for Pyppeteer)
echo "Installing headless Chromium for Pyppeteer..."
python -c "import pyppeteer; pyppeteer.install()"

echo "✅ Environment setup complete."
