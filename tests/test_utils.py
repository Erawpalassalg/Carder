from carder import utils


def test_mm2px():
    pass


def test_rect2size():
    rect = (0, 0, 1, 1)
    assert utils.rect2size(rect) == (1, 1)


def test_rect2pos():
    rect = (0, 0, 1, 1)
    assert utils.rect2pos(rect) == (0, 0)
