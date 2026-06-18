"""
ats_knowledge.py
Contains static explanations for ATS-hostile formatting flags.
"""

ATS_FLAG_EXPLANATIONS = {
    "tables_detected": "Some parsers, including older Workday configurations, read across columns rather than down a single one, which can scramble word order on import.",
    "images_detected": "ATS systems strip all visual elements, and image-based text is completely ignored.",
    "text_in_table": "Content inside table cells is frequently skipped entirely by Taleo and several other widely-used ATS platforms.",
    "invisible_text": "Hidden or white-on-white text is sometimes flagged as an attempt to game keyword matching, rather than silently ignored.",
    "header_footer_content": "Content placed in Word header or footer regions is skipped by most ATS parsers — contact info here may never be extracted.",
    "graphic_skill_ratings": "Star or bar icons used to indicate skill level aren't read as text by most parsers — the skill may register as entirely missing.",
    "non_standard_font": "Decorative or uncommon fonts can cause character substitution in some parsers, garbling keywords even when the resume looks correct visually.",
}
