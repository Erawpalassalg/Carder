INCH: float = 25.4  # mm


def mm2px(*args, dpi: float):
    """Return px from milimeters, according to DPI

    see https://pixelcalculator.com/en
    """

    def _mm2px(mm: float, dpi: int) -> int:
        return int(dpi * mm / INCH)

    if len(args) > 1:
        return tuple(_mm2px(arg, dpi) for arg in args)

    try:
        return tuple(_mm2px(arg, dpi) for arg in args[0])
    except TypeError:
        pass

    return _mm2px(args[0], dpi)


def rect2size(rect: tuple) -> tuple:
    """Return a (height, width) tuple from a rectangle tuple"""
    return (rect[2] - rect[0], rect[3] - rect[1])


def rect2pos(rect: tuple) -> tuple:
    """Return a (x_pos, y_pos) tuple from a rectangle tuple"""
    return rect[:2]
