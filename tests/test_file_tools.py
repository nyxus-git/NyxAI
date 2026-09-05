"""Tests for file system tools."""
import os
import tempfile
import pytest

from tools.files.fs_tools import list_directory, read_file

def test_list_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test file and dir
        os.makedirs(os.path.join(temp_dir, "subdir"))
        with open(os.path.join(temp_dir, "test.txt"), "w") as f:
            f.write("test")
            
        res = list_directory(temp_dir)
        assert res.success is True
        assert "subdir/" in res.display_text
        assert "test.txt" in res.display_text

def test_read_file():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("hello world")
        tmp_path = f.name
        
    try:
        res = read_file(tmp_path)
        assert res.success is True
        assert "hello world" in res.display_text
    finally:
        os.unlink(tmp_path)

def test_read_file_too_large():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("a" * 31000)
        tmp_path = f.name
        
    try:
        res = read_file(tmp_path)
        assert res.success is False
        assert "too large" in res.error
    finally:
        os.unlink(tmp_path)
