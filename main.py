import os
import time
import logging
import argparse
import signal
import sys
from google import genai
from google.genai import types
from rich.console import Console

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "transcription.log")

# Configure logging to output to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console()

DATA_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(DATA_DIR, exist_ok=True)
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def generate(input_url: str, prompt_text: str, api_key: str, output_dir: str):
    logger.info("For input I will use url '%s'", input_url)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Extract filename from the URL
    input_url_filename = os.path.basename(input_url)
    # Sanitize filename to remove invalid characters
    input_url_filename = input_url_filename.replace("%2F", "_")
    # Shorten if too long
    if len(input_url_filename) > 255:
        input_url_filename = input_url_filename[:255]
    logger.info("Extracted filename: %s", input_url_filename)

    client = genai.Client(
        api_key=api_key
    )

    # Use the provided prompt text
    prompt = prompt_text.replace("INPUT_URL", input_url)
    logger.info("Prompt:\n%s", prompt)

    model = "gemini-3-pro-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    tools = [
        types.Tool(url_context=types.UrlContext()),
     #   types.Tool(media_context=types.MediaContext()),
   #     types.Tool(code_execution=types.ToolCodeExecution),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0,
        thinking_config=types.ThinkingConfig(
            thinking_level="LOW",
            include_thoughts=True,
        ),
        media_resolution="MEDIA_RESOLUTION_HIGH",
        tools=tools,
    )

    output_filename = os.path.join(output_dir, f"{input_url_filename}.md")
    logger.info("Saving transcription to: %s", output_filename)

    usage_metadata = None

    chunk_count = 0
    total_chars = 0
    first_chunk_time = None
    last_thought = None
    interrupted = False
    with console.status("Starting transcription...", spinner="dots") as status:
        try:
            with open(output_filename, "w", encoding="utf-8") as outfile:
                for chunk in client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                ):
                    if chunk.usage_metadata:
                        usage_metadata = chunk.usage_metadata
                    
                    if (
                        chunk.candidates is None
                        or chunk.candidates[0].content is None
                        or chunk.candidates[0].content.parts is None
                    ):
                        continue
                    
                    part = chunk.candidates[0].content.parts[0]
                    
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                    
                    is_thought = False
                    if hasattr(part, "thought") and part.thought:
                        is_thought = True
                        if isinstance(part.thought, bool) and part.text:
                            last_thought = part.text
                        elif isinstance(part.thought, str):
                            last_thought = part.thought
                    
                    if not is_thought and part.text:
                        text_chunk = part.text
                        outfile.write(text_chunk)
                        chunk_count += 1
                        total_chars += len(text_chunk)
                        
                    elapsed_time = time.time() - first_chunk_time
                    token_info = ""
                    if usage_metadata:
                        token_info = f", Tokens: {usage_metadata.total_token_count}"
                    
                    thought_info = ""
                    if last_thought:
                        thought_info = f" | Thinking: {last_thought.replace('\n', ' ')}..."

                    status.update(f"Transcribing... (Chunks: {chunk_count}, Chars: {total_chars}, Time: {elapsed_time:.1f}s{token_info}{thought_info})")
        except (KeyboardInterrupt, SystemExit):
            logger.warning("\nTranscription interrupted by user or system.")
            interrupted = True
    
    if first_chunk_time:
        logger.info("Time elapsed: %.2fs", time.time() - first_chunk_time)
        
    if usage_metadata:
        logger.info("Total token usage: %d", usage_metadata.total_token_count)

    if not interrupted:
        logger.info("Transcription saved successfully.")
    else:
        logger.info("Transcription partially saved due to interruption.")

    # Save meta information
    meta_filename = os.path.join(output_dir, f"{input_url_filename}.meta.txt")
    logger.info("Saving meta information to: %s", meta_filename)
    with open(meta_filename, "w", encoding="utf-8") as metafile:
        metafile.write(f"Model: {model}\n")
        metafile.write("Configuration:\n")
        metafile.write(f"  Temperature: {generate_content_config.temperature}\n")
        metafile.write(f"  Thinking Config Thinking Level: {generate_content_config.thinking_config.thinking_level}\n")
        metafile.write(f"  Thinking Config Include Thoughts: {generate_content_config.thinking_config.include_thoughts}\n")
        metafile.write(f"  Thinking Config Thinking Budget: {generate_content_config.thinking_config.thinking_budget}\n")
        metafile.write(f"  Media Resolution: {generate_content_config.media_resolution}\n")
        metafile.write(f"  Tools: {', '.join(str(tool) for tool in generate_content_config.tools)}\n")
        metafile.write("\n")
        metafile.write(f"Prompt:\n{prompt}\n")
        metafile.write("\n")
        metafile.write(f"Input URL:\n{input_url}\n")
        metafile.write("\n")
        if usage_metadata:
            metafile.write("Usage Metadata:\n")
            metafile.write(f"  Prompt Token Count: {usage_metadata.prompt_token_count}\n")
            metafile.write(f"  Candidates Token Count: {usage_metadata.candidates_token_count}\n")
            metafile.write(f"  Total Token Count: {usage_metadata.total_token_count}\n")
        else:
            metafile.write("Usage Metadata: Not available\n")
            
    logger.info("Meta information saved successfully.")

def main():
    parser = argparse.ArgumentParser(description="Transcribe a file from a URL.")
    parser.add_argument("--input-url", "-i", type=str, required=True, help="The URL of the file to transcribe.")
    parser.add_argument("--prompt-file", "-pf", type=str, help="Path to the file containing the prompt.")
    parser.add_argument("--prompt", "-p", type=str, help="The prompt text to use. Overrides --prompt-file.")
    parser.add_argument("--gemini-api-key", "-gk", type=str, help="The Gemini API key to use. Overrides the GEMINI_API_KEY environment variable.")
    parser.add_argument("--output-directory", "-o", type=str, default=DATA_DIR, help=f"The directory where the transcription and meta file will be written to. Otherwise write to sub-directory {DATA_DIR}/.")
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
        parser.error("Gemini API key must be provided via --gemini-api-key or the GEMINI_API_KEY environment variable.")

    generate(input_url=args.input_url, prompt_text=prompt_text, api_key=gemini_api_key, output_dir=args.output_directory)

if __name__ == "__main__":
    main()