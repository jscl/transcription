import os

from src import utils


def test_parse_pages_single():
    assert utils.parse_pages("1") == [0]
    assert utils.parse_pages("5") == [4]

def test_parse_pages_list():
    assert utils.parse_pages("1, 3, 5") == [0, 2, 4]

def test_parse_pages_range():
    assert utils.parse_pages("1-3") == [0, 1, 2]

def test_parse_pages_mixed():
    assert utils.parse_pages("1-3, 5") == [0, 1, 2, 4]

def test_parse_pages_unordered():
    assert utils.parse_pages("5, 1") == [0, 4]

def test_get_unique_filename_no_collision(tmp_path):
    f = tmp_path / "test.txt"
    # File doesn't exist
    assert utils.get_unique_filename(str(f), overwrite=False) == str(f)

def test_get_unique_filename_overwrite(tmp_path):
    f = tmp_path / "test.txt"
    f.touch()
    # File exists but overwrite is True
    assert utils.get_unique_filename(str(f), overwrite=True) == str(f)

def test_get_unique_filename_collision(tmp_path):
    f = tmp_path / "test.txt"
    f.touch()
    # File exists and overwrite is False
    unique = utils.get_unique_filename(str(f), overwrite=False)
    assert unique != str(f)
    assert "test_" in unique
    assert ".txt" in unique
    assert os.path.dirname(unique) == str(tmp_path)
