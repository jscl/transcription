"""
Module for processing PDF files (page selection, redaction).
"""

import logging
import os

import pymupdf
from src.utils import parse_pages

logger = logging.getLogger(__name__)

def process_pdf(input_path: str, pages_arg: str | None, keep_ocr: bool, output_dir: str) -> str:
    """
    Processes a PDF: selects pages (unless keep_ocr is True).
    Returns the path to the processed PDF.
    """
    logger.info("Processing PDF: %s", input_path)
    doc = pymupdf.open(input_path)
    
    # Select pages
    if pages_arg:
        selected_pages = parse_pages(pages_arg)
        # Validate page numbers
        max_page = len(doc) - 1
        selected_pages = [p for p in selected_pages if 0 <= p <= max_page]
        if not selected_pages:
            raise ValueError("No valid pages selected.")
        doc.select(selected_pages)
        logger.info("Selected %d pages: %s", len(doc), ", ".join(str(int(p + 1)) for p in selected_pages))

    output_filename = os.path.basename(input_path)
    if not keep_ocr:
        # Use redaction to remove text but keep images and graphics
        logger.info("Applying redactions to remove text/OCR layer...")
        for page in doc:
            page.add_redact_annot(page.rect)
            page.apply_redactions(
                images=0, #pymupdf.PDF_REDACT_IMAGE_NONE,  # fail-safe: keep images
                graphics=0#pymupdf.PDF_REDACT_LINE_ART_NONE  # fail-safe: keep vector graphics
            )
        
        output_filename = f"processed_{output_filename}"
    
    output_path = os.path.join(output_dir, output_filename)
    doc.ez_save(output_path)
    doc.close()
    logger.info("Saved processed PDF to: %s", output_path)
    return output_path
