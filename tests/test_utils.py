"""
Unit tests for the utils module.
"""

from src import utils


def test_parse_pages_single():
    """Test parsing a single page number."""
    assert utils.parse_pages("1") == [0]
    assert utils.parse_pages("5") == [4]

def test_parse_pages_list():
    """Test parsing a comma-separated list of pages."""
    assert utils.parse_pages("1, 3, 5") == [0, 2, 4]

def test_parse_pages_range():
    """Test parsing a range of pages."""
    assert utils.parse_pages("1-3") == [0, 1, 2]

def test_parse_pages_mixed():
    """Test parsing mixed ranges and single pages."""
    assert utils.parse_pages("1-3, 5") == [0, 1, 2, 4]

def test_parse_pages_unordered():
    """Test parsing unordered pages returns sorted list."""
    assert utils.parse_pages("5, 1") == [0, 4]
