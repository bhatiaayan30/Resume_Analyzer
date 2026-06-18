from unittest.mock import MagicMock, patch

import pytest

from analyzer.utils import analyze_with_ai


@patch("analyzer.utils.Groq")
def test_analyze_with_ai_success(mock_groq_class):
    mock_client = mock_groq_class.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = """{
        "match_score": 85,
        "matched_skills": ["Python", "Django"],
        "missing_skills": ["Docker"],
        "experience_gaps": ["No deployment experience"],
        "suggestions": ["Learn Docker"],
        "upskill_paths": [],
        "impact_critiques": []
    }"""
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_client.chat.completions.create.return_value = mock_response

    # Run the function
    result, usage = analyze_with_ai("Resume with Python and Django", "Job needs Python, Django, Docker")

    # Verify
    assert result["match_score"] == 85
    assert "Python" in result["matched_skills"]
    assert "Docker" in result["missing_skills"]
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50


@patch("analyzer.utils.Groq")
def test_analyze_with_ai_malformed_json(mock_groq_class):
    mock_client = mock_groq_class.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Not a JSON object"
    mock_client.chat.completions.create.return_value = mock_response

    import pytest

    with pytest.raises(Exception):
        analyze_with_ai("Resume", "Job")
