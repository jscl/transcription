#!/bin/bash

# Default values
DEFAULT_FILE="https://archive.org/download/sim_die-mennonitische-rundschau_1888-01-18_9_3/sim_die-mennonitische-rundschau_1888-01-18_9_3.pdf"
DEFAULT_PROMPT="prompts/transcribeurl.txt"

# Run the transcription script
# Extra arguments passed to this script will be forwarded to main.py
uv run python main.py \
  --input-file "$DEFAULT_FILE" \
  --prompt-file "$DEFAULT_PROMPT" \
  "$@"
