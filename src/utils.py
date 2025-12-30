"""
Utility functions for file handling and processing.
"""

import os
import logging
import requests
from rich.progress import Progress, SpinnerColumn, TextColumn,BarColumn, TaskProgressColumn
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

def download_file(url: str, output_dir: str) -> str:
    """
    Downloads a file from a URL to a specified output directory with a progress bar.

    Args:
        url (str): The URL of the file to download.
        output_dir (str): The directory where the file should be saved.

    Returns:
        str: The local path to the downloaded file.
    """
    logger.info("Downloading file from: %s", url)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    filename = url.split("/")[-1]
    # Basic sanitization
    filename = filename.split("?")[0] 
    local_path = os.path.join(output_dir, filename)
    if os.path.exists(local_path):
        logger.info("File already exists: %s. Skipping download.", local_path)
        return local_path
    
    with requests.get(url, stream=True, timeout=30) as response:
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
                    
    logger.info("Downloaded file to: %s", local_path)
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
