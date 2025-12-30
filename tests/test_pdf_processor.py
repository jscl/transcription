"""
Integration tests for the PDF processor module using real PDF artifacts.
"""

import os
import pytest
import pymupdf
from src import pdf_processor

TEST_PDF_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "test.pdf")

def test_process_pdf_split_all(tmp_path):
    """
    Test processing the 'test.pdf' without page selection.
    It should split all pages into separate files.
    When keep_ocr is False (default), text should be removed (redacted).
    """
    output_dir = str(tmp_path)
    
    # Ensure test artifact exists
    assert os.path.exists(TEST_PDF_PATH), f"Test artifact not found at {TEST_PDF_PATH}"
    
    # Check original page count and ensure it has text initially for valid testing
    with pymupdf.open(TEST_PDF_PATH) as doc:
        original_page_count = 3
        # Verify input has some text to begin with, otherwise the test is meaningless
        start_text = ""
        for page in doc:
             start_text += page.get_text()
    
    if not start_text.strip():
        pytest.skip("Test PDF has no text/OCR layer to verify redaction against.")

    # Process with keep_ocr=False
    result_paths = pdf_processor.process_pdf(
        TEST_PDF_PATH, pages_arg=None, keep_ocr=False, output_dir=output_dir
    )
    
    # Verify results
    assert len(result_paths) == original_page_count
    
    for i, path in enumerate(result_paths):
        assert os.path.exists(path)
        expected_name = f"test_page_{i+1}.pdf"
        assert os.path.basename(path) == expected_name
        
        # Verify valid PDF and NO TEXT (redacted)
        try:
            with pymupdf.open(path) as page_doc:
                assert len(page_doc) == 1
                page_text = page_doc[0].get_text()
                # We expect redaction to remove text
                assert not page_text.strip(), f"Page {i+1} should have empty text after redaction, found: {page_text[:100]}..."
        except Exception as e:
            pytest.fail(f"Generated file {path} inspection failed: {e}")

def test_process_pdf_select_pages(tmp_path):
    """
    Test processing 'test.pdf' with specific page selection.
    When keep_ocr is True, text should be preserved.
    """
    output_dir = str(tmp_path)
    # Select first page
    pages_arg = "1" 
    
    # Process with keep_ocr=True
    result_paths = pdf_processor.process_pdf(
        TEST_PDF_PATH, pages_arg=pages_arg, keep_ocr=True, output_dir=output_dir
    )
    
    assert len(result_paths) == 1
    path = result_paths[0]
    assert os.path.exists(path)
    # When keep_ocr=True, filename doesn't have "processed_" prefix
    assert os.path.basename(path) == "test_page_1.pdf"

    try:
        with pymupdf.open(path) as page_doc:
            assert len(page_doc) == 1
            page_text = page_doc[0].get_text()
            # We expect text to be present
            assert page_text.strip(), "Page 1 should have text when keep_ocr=True"
    except Exception as e:
        pytest.fail(f"Generated file {path} inspection failed: {e}")

def test_process_pdf_invalid_pages(tmp_path):
    """
    Test invalid page selection.
    """
    output_dir = str(tmp_path)
    
    with pymupdf.open(TEST_PDF_PATH) as doc:
        max_page = len(doc)
    
    invalid_page = str(max_page + 10)
    
    with pytest.raises(ValueError):
        pdf_processor.process_pdf(
            TEST_PDF_PATH, pages_arg=invalid_page, keep_ocr=False, output_dir=output_dir
        )
