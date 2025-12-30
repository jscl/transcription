"""
Module for handling Gemini transcription.
"""

import logging
import os
import time
import sys
from google import genai
from google.genai import types
from rich.console import Console

from src.pdf_processor import process_pdf
from src.utils import download_file

logger = logging.getLogger(__name__)
console = Console()

def transcribe(
        input_file: str | None,
        prompt_text: str,
        api_key: str,
        output_dir: str,
        pages: str | None = None,
        keep_ocr: bool = False,
        overwrite: bool = False
    ):
    """
    Generates transcription from a file or URL using Google Gemini.
    """
    if not input_file:
        raise ValueError("input_file must be provided.")

    input_file_local = input_file
    is_downloaded_file = input_file.startswith("http://") or input_file.startswith("https://")
    if is_downloaded_file:
        # Download the file first
        try:
            input_file_local = download_file(input_file, output_dir)
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.error("Failed to download file: %s", e)
            sys.exit(1)

    file_uri_to_delete = None
    user_content_part = None
    logger.info("Using local file: %s", input_file_local)
    input_file_name = os.path.basename(input_file_local)
    output_filename = os.path.join(output_dir, f"{input_file_name}.md")
    if not overwrite and os.path.exists(output_filename):
        logger.info(
            "Output file '%s' already exists. Skipping processing.",
            output_filename
        )
        return
    
    logger.info("Starting transcription process...")
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    client = genai.Client(
        api_key=api_key
    )

    processed_file_path = input_file_local
    if input_file_local.lower().endswith(".pdf"):
        # Process PDF (select pages, rasterize)
        processed_file_path = process_pdf(input_file_local, pages, keep_ocr, output_dir)
         
    logger.info("Uploading file: %s", processed_file_path)
    uploaded_file = client.files.upload(file=processed_file_path)
    logger.info("Uploaded file as: %s", uploaded_file.uri)
    file_uri_to_delete = uploaded_file.name # Save for cleanup
        
    # Prepare content for Gemini
    user_content_part = types.Part.from_uri(
        file_uri=uploaded_file.uri,
        mime_type=uploaded_file.mime_type
    )

    # Use the provided prompt text
    replacement = "Local file: " + input_file_name
    if pages:
        replacement = f"{replacement} containing pages: {pages}"
    prompt = prompt_text.replace("INPUT_URL", replacement)

    logger.debug("Prompt:\n%s", prompt)

    model = "gemini-3-pro-preview"
    
    parts = [types.Part.from_text(text=prompt)]
    if user_content_part:
        parts.append(user_content_part)
        
    contents = [
        types.Content(
            role="user",
            parts=parts,
        ),
    ]
    
    generate_content_config = types.GenerateContentConfig(
        temperature=0,
        thinking_config=types.ThinkingConfig(
            thinking_level="LOW",
            include_thoughts=True,
        ),
        media_resolution="MEDIA_RESOLUTION_HIGH",
    )


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

                    status.update(
                        f"Transcribing... (Chunks: {chunk_count}, "
                        f"Chars: {total_chars}, Time: {elapsed_time:.1f}s"
                        f"{token_info}{thought_info})"
                    )
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
    output_basename = os.path.basename(output_filename)
    if output_basename.endswith(".md"):
        meta_stem = output_basename[:-3] # remove .md
    else:
        meta_stem = output_basename
    meta_filename = os.path.join(output_dir, f"{meta_stem}.meta.txt")
    
    logger.info("Saving meta information to: %s", meta_filename)
    with open(meta_filename, "w", encoding="utf-8") as metafile:
        metafile.write(f"Model: {model}\n")
        metafile.write("Configuration:\n")
        metafile.write(f"  Temperature: {generate_content_config.temperature}\n")
        metafile.write(
            f"  Thinking Config Thinking Level: "
            f"{generate_content_config.thinking_config.thinking_level}\n"
        )
        metafile.write(
            f"  Thinking Config Include Thoughts: "
            f"{generate_content_config.thinking_config.include_thoughts}\n"
        )
        metafile.write(
            f"  Thinking Config Thinking Budget: "
            f"{generate_content_config.thinking_config.thinking_budget}\n"
        )
        metafile.write(f"  Media Resolution: {generate_content_config.media_resolution}\n")
        if generate_content_config.tools:
            metafile.write(
                f"  Tools: {', '.join(str(tool) for tool in generate_content_config.tools)}\n"
            )
        metafile.write("\n")
        metafile.write(f"Prompt:\n{prompt}\n")
        metafile.write("\n")
        if input_file_local:
            metafile.write(f"Input File: {input_file_name}\n")
        if is_downloaded_file:
            metafile.write(f"Downloaded from: {input_file}\n")
        metafile.write("\n")
        if usage_metadata:
            metafile.write("Usage Metadata:\n")
            metafile.write(f"  Prompt Token Count: {usage_metadata.prompt_token_count}\n")
            metafile.write(f"  Candidates Token Count: {usage_metadata.candidates_token_count}\n")
            metafile.write(f"  Total Token Count: {usage_metadata.total_token_count}\n")
        else:
            metafile.write("Usage Metadata: Not available\n")
            
    logger.info("Meta information saved successfully.")

    if file_uri_to_delete:
        try:
            client.files.delete(name=file_uri_to_delete)
            logger.info("Deleted remote file: %s", file_uri_to_delete)
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.warning("Failed to delete remote file: %s", e)
