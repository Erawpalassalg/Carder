from tests.utils import RESOLUTION

from carder.carder import DEFAULT_FONT
from carder.utils import mm2px
from carder.PIL import fit_text_to_rect


def test_fit_text_to_rect():
    """Test fit text to rect"""
    text = "abcd efgh"
    rect = mm2px([0, 0, 10, 10], dpi=RESOLUTION)
    reformatted_text = fit_text_to_rect(text, DEFAULT_FONT, rect)
    assert reformatted_text == text.replace(" ", "\n")
