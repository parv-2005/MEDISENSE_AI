from app.services.ocr.cleaner import clean_text


def test_collapses_runs_of_spaces_and_tabs():
    assert clean_text("Hemoglobin   \t 13.5   g/dL") == "Hemoglobin 13.5 g/dL"


def test_normalises_windows_line_endings_and_trims_lines():
    assert clean_text("  WBC 7.2 \r\n  RBC 4.8  \r\n") == "WBC 7.2\nRBC 4.8"


def test_collapses_three_or_more_blank_lines_to_one():
    assert clean_text("A\n\n\n\n\nB") == "A\n\nB"


def test_joins_hyphenated_line_breaks():
    assert clean_text("haemo-\nglobin low") == "haemoglobin low"


def test_fixes_common_ocr_digit_confusions_inside_numbers():
    # 'O' and 'l' between digits are almost always 0 and 1 in lab values
    assert clean_text("Glucose 1O5 mg/dL, Platelets 25l") == "Glucose 105 mg/dL, Platelets 251"


def test_removes_form_feed_and_control_chars():
    assert clean_text("Page 1\x0cPage 2\x00") == "Page 1\nPage 2"


def test_empty_input_returns_empty_string():
    assert clean_text("") == ""
    assert clean_text("   \n\n  ") == ""
