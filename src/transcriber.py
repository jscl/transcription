"""
Module for handling Gemini transcription with parallel processing support.
"""

import logging
import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor
from google import genai
from google.genai import types
from rich.console import Console

from src.pdf_processor import process_pdf
from src.utils import download_file

logger = logging.getLogger(__name__)
console = Console()
MAX_PARALLEL_PAGES = 10

def _process_single_chunk(
    api_key: str,
    file_path: str,
    prompt: str,
    model: str
) -> dict:
    """
    Uploads a file, generates content, and cleans up.
    Returns a dictionary with 'text', 'usage_metadata', 'thought'.
    """
    client = genai.Client(api_key=api_key)
    
    filename = os.path.basename(file_path)
    logger.info("Uploading file chunk: %s", filename)
    
    try:
        uploaded_file = client.files.upload(file=file_path)
        logger.debug("Uploaded %s as: %s", filename, uploaded_file.uri)
    except Exception as e:
        logger.error("Failed to upload %s: %s", filename, e)
        return {"text": f"[Error uploading {filename}: {e}]", "usage_metadata": None, "thought": None}

    try:
        user_content_part = types.Part.from_uri(
            file_uri=uploaded_file.uri,
            mime_type=uploaded_file.mime_type
        )
        
        parts = [types.Part.from_text(text=prompt), user_content_part]
        
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
        
        logger.info("Generating content for: %s", filename)
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        text_content = ""
        thought_content = ""
        
        # Parse response
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "thought") and part.thought:
                    if isinstance(part.thought, bool) and part.text:
                         thought_content += part.text
                    elif isinstance(part.thought, str):
                        thought_content += part.thought
                elif part.text:
                    text_content += part.text
        
        return {
            "text": text_content, 
            "usage_metadata": response.usage_metadata,
            "thought": thought_content
        }

    except Exception as e:
        logger.error("Failed to generate content for %s: %s", filename, e)
        return {"text": f"[Error generating for {filename}: {e}]", "usage_metadata": None, "thought": None}
    finally:
        # Cleanup
        try:
            client.files.delete(name=uploaded_file.name)
            logger.debug("Deleted remote file: %s", uploaded_file.name)
        except Exception as e:
            logger.warning("Failed to delete remote file %s: %s", uploaded_file.name, e)


def transcribe(
        input_file: str | None,
        prompt_text: str,
        api_key: str,
        output_dir: str,
        pages: str | None = None,
        keep_ocr: bool = False,
        overwrite: bool = False,
        parallel_pages: int = MAX_PARALLEL_PAGES,
        delete_temporary_files: bool = True
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
    
    files_to_process = []
    
    if input_file_local.lower().endswith(".pdf"):
        # Process PDF (select pages, rasterize, split)
        # process_pdf now returns a list of paths
        files_to_process = process_pdf(input_file_local, pages, keep_ocr, output_dir)
    else:
        files_to_process = [input_file_local]
        
    # Prepare prompt
    replacement = "Local file: " + input_file_name
    if pages:
        replacement = f"{replacement} containing pages: {pages}"
    base_prompt = prompt_text.replace("INPUT_URL", replacement)
    
    # Run parallel processing
    model = "gemini-3-pro-preview"
    results = [None] * len(files_to_process)
    
    start_time = time.time()
    
    # We define a helper to map index to result to preserve order
    def process_wrapper(index, fpath):
        return index, _process_single_chunk(api_key, fpath, base_prompt, model)

    logger.info("Processing %d files in parallel...", len(files_to_process))
    
    total_tokens = 0
    final_text = ""
    
    with console.status(f"Processing {len(files_to_process)} parts in parallel (Model: {model})...", spinner="dots") as status:
        with ThreadPoolExecutor(max_workers=min(len(files_to_process), parallel_pages)) as executor:
            future_to_file = {
                executor.submit(process_wrapper, i, FilePath): FilePath 
                for i, FilePath in enumerate(files_to_process)
            }
            
            completed_count = 0
            for future in future_to_file:
                # Wait for completion
                try:
                    idx, result = future.result()
                    results[idx] = result
                    completed_count += 1
                    status.update(f"Processing... ({completed_count}/{len(files_to_process)} parts completed)")
                except Exception as e:
                    logger.error("Thread failed: %s", e)
    
    elapsed_time = time.time() - start_time
    logger.info("All parts processed in %.2fs", elapsed_time)
    
    # Aggregate results
    full_transcript = []
    combined_thoughts = []
    
    for i, res in enumerate(results):
        if not res:
            full_transcript.append(f"\n\n[Missing part {i+1}]\n\n")
            continue
            
        if len(files_to_process) > 1:
            full_transcript.append(f"\n\n## Page {i+1}\n\n")
            
        full_transcript.append(res['text'])
        
        if res.get('thought'):
            combined_thoughts.append(f"Page {i+1} Thought: {res['thought'][:200]}...")
            
        if res.get('usage_metadata'):
            total_tokens += res['usage_metadata'].total_token_count

    final_text = "".join(full_transcript)
    
    # Save transcription
    logger.info("Saving transcription to: %s", output_filename)
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(final_text)
        
    logger.info("Total token usage: %d", total_tokens)
    logger.info("Transcription saved successfully.")

    # Save meta information
    output_basename = os.path.basename(output_filename)
    if output_basename.endswith(".md"):
        meta_stem = output_basename[:-3]
    else:
        meta_stem = output_basename
    meta_filename = os.path.join(output_dir, f"{meta_stem}.meta.txt")
    
    logger.info("Saving meta information to: %s", meta_filename)
    with open(meta_filename, "w", encoding="utf-8") as metafile:
        metafile.write(f"Model: {model}\n")
        metafile.write("Configuration:\n")
        metafile.write("Parallel Processing: Yes\n")
        metafile.write(f"Parts: {len(files_to_process)}\n")
        metafile.write("\n")
        metafile.write(f"Prompt:\n{base_prompt}\n")
        metafile.write("\n")
        if input_file_local:
            metafile.write(f"Input File: {input_file_name}\n")
        if is_downloaded_file:
            metafile.write(f"Downloaded from: {input_file}\n")
        metafile.write("\n")
        metafile.write(f"Total Token Count: {total_tokens}\n")
            
    logger.info("Meta information saved successfully.")
    
    if delete_temporary_files and input_file_local.lower().endswith(".pdf") and len(files_to_process) > 0:
        logger.info("Cleaning up temporary page files...")
        for fpath in files_to_process:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception as e: # pylint: disable=broad-exception-caught
                logger.warning("Failed to delete temporary file %s: %s", fpath, e)
        logger.info("Temporary files cleaned up.")
