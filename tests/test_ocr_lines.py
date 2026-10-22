"""OCR row reconstruction: boxes on the same visual line must end up on one text line."""
from extractor.ocr import _ocr_lines

# (x0, top, x1, bottom, text, confidence) in PDF points, deliberately out of order
BOXES = (
    (300, 101, 340, 113, "75.00", 0.95),
    (40, 100, 150, 112, "Consulting hours", 0.97),
    (240, 99, 260, 111, "20", 0.45),
    (40, 130, 120, 142, "Grand Total:", 0.99),
    (300, 131, 360, 143, "2,171.20", 0.30),
)


def test_rows_rebuilt_left_to_right_with_confidence_markers():
    lines, confs = _ocr_lines(BOXES, min_confidence=0.5)
    assert lines == ["Consulting hours   [?20?]   75.00", "Grand Total:"]
    assert len(confs) == 4  # the 0.30 box is dropped while better boxes exist


def test_all_low_confidence_falls_back_instead_of_empty():
    lines, _ = _ocr_lines(((10, 10, 50, 20, "TOTAL", 0.2),), min_confidence=0.5)
    assert lines == ["[??TOTAL??]"]
