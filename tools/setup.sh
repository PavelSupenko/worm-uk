#!/usr/bin/env bash
# Prepares a Mac for the voiceover tools. Safe to run again: whatever is
# already in place is skipped.
#   - Homebrew packages: ffmpeg (audio), whisper.cpp (local speech recognition)
#   - the whisper.cpp model, downloaded to ~/.cache/whisper and checked by hash
#   - credentials in the environment (never printed) and a connection check
# Usage: tools/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_DIR="${WHISPER_MODEL_DIR:-$HOME/.cache/whisper}"
MODEL_NAME="ggml-large-v3-turbo-q5_0.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME"
MODEL_SHA256="394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"
VARIABLES="ELEVENLABS_API_KEY R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET R2_PUBLIC_URL"

echo "== Packages"
if ! command -v brew >/dev/null; then
    echo "Homebrew is missing: install it from https://brew.sh and run this script again"
    exit 1
fi
for package in ffmpeg whisper.cpp; do
    if brew list --versions "$package" >/dev/null; then
        echo "$package: installed"
    else
        brew install "$package"
    fi
done
python3 -c 'import sys; assert sys.version_info >= (3, 8), "Python 3.8+ is needed"; print("python3:", sys.version.split()[0])'

echo "== Speech recognition model"
model="$MODEL_DIR/$MODEL_NAME"
if [ -f "$model" ] && [ "$(shasum -a 256 "$model" | cut -d' ' -f1)" = "$MODEL_SHA256" ]; then
    echo "$model: present"
else
    mkdir -p "$MODEL_DIR"
    echo "downloading $MODEL_NAME (~550 MB) from $MODEL_URL"
    curl -L --fail --progress-bar -o "$model.part" "$MODEL_URL"
    if [ "$(shasum -a 256 "$model.part" | cut -d' ' -f1)" != "$MODEL_SHA256" ]; then
        rm -f "$model.part"
        echo "the downloaded model has an unexpected checksum, removed it"
        exit 1
    fi
    mv "$model.part" "$model"
    echo "$model: downloaded"
fi

echo "== Credentials"
missing=0
for name in $VARIABLES; do
    if [ -n "${!name:-}" ]; then
        echo "$name: set"
    else
        echo "$name: missing (add 'export $name=...' to ~/.zshrc and restart the terminal / Claude Code)"
        missing=1
    fi
done
if [ -n "${ELEVENLABS_API_KEY:-}" ]; then
    status=$(curl -s -o /dev/null -w '%{http_code}' -H @- https://api.elevenlabs.io/v1/user/subscription <<< "xi-api-key: $ELEVENLABS_API_KEY")
    echo "ElevenLabs: HTTP $status (200 means the key works and may read the account)"
fi
if [ -n "${R2_BUCKET:-}" ] && [ -n "${R2_SECRET_ACCESS_KEY:-}" ]; then
    python3 tools/r2.py check
fi
[ "$missing" = 0 ] && echo "== Ready" || echo "== Set the missing variables, then run tools/setup.sh again"
