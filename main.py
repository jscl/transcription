import os
import time
import logging
import argparse
import fitz  # pymupdf
import requests
from google import genai
from google.genai import types
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

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

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def download_file(url: str, output_dir: str) -> str:
    """Downloads a file from a URL to the output directory with a progress bar."""
    logger.info(f"Downloading file from: {url}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    filename = url.split("/")[-1]
    # Basic sanitization
    filename = filename.split("?")[0] 
    local_path = os.path.join(output_dir, filename)
    
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Downloading {filename}...", total=total_size)
            
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))
                    
    logger.info(f"Downloaded file to: {local_path}")
    return local_path

def parse_pages(pages_arg: str) -> list[int]:
    """Parses a string of page ranges (e.g., '1-3, 5') into a list of 0-indexed page numbers."""
    pages = set()
    parts = pages_arg.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.update(range(start - 1, end))
        else:
            pages.add(int(part) - 1)
    return sorted(list(pages))

def process_pdf(input_path: str, pages_arg: str | None, keep_ocr: bool, output_dir: str) -> str:
    """
    Processes a PDF: selects pages and rasterizes them (unless keep_ocr is True).
    Returns the path to the processed PDF.
    """
    logger.info(f"Processing PDF: {input_path}")
    doc = fitz.open(input_path)
    
    # Select pages
    if pages_arg:
        selected_pages = parse_pages(pages_arg)
        # Validate page numbers
        max_page = len(doc) - 1
        selected_pages = [p for p in selected_pages if 0 <= p <= max_page]
        if not selected_pages:
             raise ValueError("No valid pages selected.")
        doc.select(selected_pages)
        logger.info(f"Selected {len(doc)} pages.")

    output_filename = os.path.basename(input_path)
    if not keep_ocr:
        # Use redaction to remove text but keep images and graphics
        logger.info("Applying redactions to remove text/OCR layer...")
        for page in doc:
            page.add_redact_annot(page.rect)
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,  # fail-safe: keep images
                graphics=fitz.PDF_REDACT_LINE_ART_NONE  # fail-safe: keep vector graphics
            )
        
        output_filename = f"processed_{output_filename}"
    
    output_path = os.path.join(output_dir, output_filename)
    doc.ez_save(output_path)
    doc.close()
    logger.info(f"Saved processed PDF to: {output_path}")
    return output_path

def generate(input_url: str | None, input_file: str | None, prompt_text: str, api_key: str, output_dir: str, pages: str | None = None, keep_ocr: bool = False):
    logger.info("Starting generation process...")
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    client = genai.Client(
        api_key=api_key
    )

    file_uri_to_delete = None

    if input_file:
         logger.info("Using local file: %s", input_file)
         input_name = os.path.basename(input_file)
         
         processed_file_path = input_file
         if input_file.lower().endswith(".pdf"):
             # Process PDF (select pages, rasterize)
             processed_file_path = process_pdf(input_file, pages, keep_ocr, output_dir)
         
         logger.info(f"Uploading file: {processed_file_path}")
         uploaded_file = client.files.upload(file=processed_file_path)
         logger.info(f"Uploaded file as: {uploaded_file.uri}")
         file_uri_to_delete = uploaded_file.name # Save for cleanup
         
         # Prepare content for Gemini
         user_content_part = types.Part.from_uri(
             file_uri=uploaded_file.uri,
             mime_type=uploaded_file.mime_type
         )
         source_identifier = input_name

    elif input_url:
        logger.info("Using input url '%s'", input_url)
        # Extract filename from the URL
        input_name = os.path.basename(input_url)
        # Sanitize filename to remove invalid characters
        input_name = input_name.replace("%2F", "_")
        # Shorten if too long
        if len(input_name) > 255:
            input_name = input_name[:255]
            
        # Prepare content for Gemini
        # Provide the URL directly as text or context?
        # The original implementation replaced INPUT_URL in the prompt.
        # We will keep that behavior but ALSO provide the URL tool if needed.
        # Note: The original code didn't actually "browse" the URL, it just put it in the prompt.
        # But it enabled UrlContext tool.
        
        user_content_part = types.Part.from_text(text=f"Process this URL: {input_url}")
        
        # Wait, the original code relied on UrlContext or just the text?
        # The prompt says "Verwende als Input folgende Datei: INPUT_URL".
        # If it's a direct download link to a PDF, the Model *might* be able to fetch it if UrlContext allows,
        # but often it's better to download user-side if we want consistency.
        # However, to preserve original behavior for URLs:
        source_identifier = input_name
        
    else:
        raise ValueError("Either input_url or input_file must be provided.")

    logger.info("Identifier: %s", source_identifier)

    # Use the provided prompt text
    if input_url:
        prompt = prompt_text.replace("INPUT_URL", input_url)
    else:
        prompt = prompt_text.replace("INPUT_URL", f"Local File: {source_identifier}")

    logger.debug("Prompt:\n%s", prompt)

    model = "gemini-3-pro-preview"
    
    parts = [types.Part.from_text(text=prompt)]
    if input_file:
        parts.append(user_content_part)
        
    contents = [
        types.Content(
            role="user",
            parts=parts,
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

    output_filename = os.path.join(output_dir, f"{source_identifier}.md")
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
    meta_filename = os.path.join(output_dir, f"{source_identifier}.meta.txt")
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
        if input_url:
            metafile.write(f"Input URL:\n{input_url}\n")
        elif input_file:
             metafile.write(f"Input File:\n{input_file}\n")
        metafile.write("\n")
        if usage_metadata:
            metafile.write("Usage Metadata:\n")
            metafile.write(f"  Prompt Token Count: {usage_metadata.prompt_token_count}\n")
            metafile.write(f"  Candidates Token Count: {usage_metadata.candidates_token_count}\n")
            metafile.write(f"  Total Token Count: {usage_metadata.total_token_count}\n")
        else:
            metafile.write("Usage Metadata: Not available\n")
            
    logger.info("Meta information saved successfully.")

    # Clean up uploaded file if strictly needed, though Gemini cleans typically after 2 days.
    # explicit deletion is nice.
    if file_uri_to_delete:
         try:
             client.files.delete(name=file_uri_to_delete)
             logger.info(f"Deleted remote file: {file_uri_to_delete}")
         except Exception as e:
             logger.warning(f"Failed to delete remote file: {e}")

def main():
    parser = argparse.ArgumentParser(description="Transcribe a file from a URL or local path.")
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-url", "-iu", type=str, help="The URL of the file to transcribe.")
    input_group.add_argument("--input-file", "-if", type=str, help="Path to a local file (image or PDF).")
    
    parser.add_argument("--pages", type=str, help="Page ranges for PDF (e.g., '1-3, 5'). Only used with --input-file for PDFs.")
    parser.add_argument("--keep-ocr", action="store_true", help="Keep embedded OCR layer in PDF. Default is to remove it (rasterize).")
    
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

    if args.input_file and (args.input_file.startswith("http://") or args.input_file.startswith("https://")):
        # Download the file first
        try:
            args.input_file = download_file(args.input_file, args.output_directory)
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            sys.exit(1)

    if args.input_url and (args.pages or args.keep_ocr):
        logger.warning("--pages and --keep-ocr are ignored when using --input-url.")

    generate(
        input_url=args.input_url,
        input_file=args.input_file,
        prompt_text=prompt_text,
        api_key=gemini_api_key,
        output_dir=args.output_directory,
        pages=args.pages,
        keep_ocr=args.keep_ocr
    )

if __name__ == "__main__":
    main()