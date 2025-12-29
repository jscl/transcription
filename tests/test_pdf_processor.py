"""
Unit tests for the PDF processor module.
"""

from unittest.mock import MagicMock, patch

import pytest

from src import pdf_processor


@patch("src.pdf_processor.fitz.open")
def test_process_pdf_no_pages_no_ocr(mock_open, tmp_path):
    """Test PDF processing without page selection and with OCR removal."""
    # Setup mock doc
    mock_doc = MagicMock()
    mock_open.return_value = mock_doc
    # len(doc) behavior
    mock_doc.__len__.return_value = 5
    
    # Mock page iteration
    mock_page = MagicMock()
    mock_doc.__iter__.return_value = iter([mock_page])
    
    output_dir = str(tmp_path)
    input_path = "test.pdf"
    
    result = pdf_processor.process_pdf(input_path, pages_arg=None, keep_ocr=False, output_dir=output_dir)
    
    # Assertions
    mock_open.assert_called_with(input_path)
    # Since keep_ocr=False, should apply redactions
    mock_page.add_redact_annot.assert_called()
    mock_page.apply_redactions.assert_called()
    
    # Should save
    mock_doc.ez_save.assert_called()
    assert "processed_test.pdf" in result

@patch("src.pdf_processor.fitz.open")
def test_process_pdf_with_pages(mock_open, tmp_path):
    """Test PDF processing with page selection."""
    mock_doc = MagicMock()
    mock_open.return_value = mock_doc
    mock_doc.__len__.return_value = 10

    output_dir = str(tmp_path)
    input_path = "test.pdf"

    pdf_processor.process_pdf(
        input_path, pages_arg="1-3", keep_ocr=True, output_dir=output_dir
    )

    # Should select pages [0, 1, 2]
    mock_doc.select.assert_called_with([0, 1, 2])

    # keep_ocr=True -> no redactions
    # ez_save should be called.
    mock_doc.ez_save.assert_called()

def test_process_pdf_invalid_pages(tmp_path):
    """Test PDF processing with invalid page selection raises error."""
    with patch("src.pdf_processor.fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_open.return_value = mock_doc
        mock_doc.__len__.return_value = 2 # 2 pages (0, 1)

        # Request page 5 -> invalid
        with pytest.raises(ValueError):
            pdf_processor.process_pdf(
                "test.pdf", pages_arg="5", keep_ocr=False, output_dir=str(tmp_path)
            )
