import os
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from analyzer.utils import extract_text

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "ats_hostile")

def test_clean_control():
    file_path = os.path.join(FIXTURES_DIR, "clean_control.docx")
    with open(file_path, "rb") as f:
        file_obj = SimpleUploadedFile(name="clean_control.docx", content=f.read(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    
    text, flags, searchability = extract_text(file_obj, ".docx")
    assert "tables_detected" not in flags
    # Basic searchability should pass since we added info
    assert any(c["passed"] for c in searchability if c["check_name"] == "Contact Information")
    assert any(c["passed"] for c in searchability if c["check_name"] == "Date Parseability")

def test_multi_column_table():
    file_path = os.path.join(FIXTURES_DIR, "multi_column_table.docx")
    with open(file_path, "rb") as f:
        file_obj = SimpleUploadedFile(name="multi_column_table.docx", content=f.read(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    
    text, flags, searchability = extract_text(file_obj, ".docx")
    assert "tables_detected" in flags
