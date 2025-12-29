"""
Main entry point for the transcription tool.
Handles command-line arguments and orchestrates the transcription process.
"""

import argparse
import logging
import os
import sys

from rich.console import Console

# Ensure src module can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.transcriber import transcribe  # pylint: disable=wrong-import-position

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "transcription.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console()
DATA_DIR = os.path.join(os.path.dirname(__file__), "output")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def main():
    """
    Main function to parse arguments and run the transcription.
    """
    parser = argparse.ArgumentParser(description="Transcribe a local file.")
    
    parser.add_argument(
        "--input-file", "-if", type=str, required=True, help="Path to a local file (image or PDF)."
    )
    
    parser.add_argument(
        "--pages", type=str,
        help="Page ranges for PDF (e.g., '1-3, 5')."
    )
    parser.add_argument(
        "--keep-ocr", action="store_true",
        help="Keep embedded OCR layer in PDF. Default is to remove it (rasterize)."
    )
    
    parser.add_argument(
        "--prompt-file", "-pf", type=str, help="Path to the file containing the prompt."
    )
    parser.add_argument(
        "--prompt", "-p", type=str, help="The prompt text to use. Overrides --prompt-file."
    )
    parser.add_argument(
        "--gemini-api-key", "-gk", type=str,
        help="The Gemini API key to use. Overrides the GEMINI_API_KEY environment variable."
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite output files if they exist. Default is to skip processing."
    )
    parser.add_argument(
        "--output-directory", "-o", type=str, default=DATA_DIR,
        help=f"The directory where the transcription and meta file will be written to. "
             f"Otherwise write to sub-directory {DATA_DIR}/."
    )

    args = parser.parse_args()

    prompt_text = None
    if args.prompt:
        prompt_text = args.prompt
    elif args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    else:
        parser.error("Either --prompt-file or --prompt must be provided.")

    gemini_api_key = args.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        parser.error(
            "Gemini API key must be provided via --gemini-api-key "
            "or the GEMINI_API_KEY environment variable."
        )

    transcribe(
        input_file=args.input_file,
        prompt_text=prompt_text,
        api_key=gemini_api_key,
        output_dir=args.output_directory,
        pages=args.pages,
        keep_ocr=args.keep_ocr,
        overwrite=args.overwrite
    )

if __name__ == "__main__":
    main()
