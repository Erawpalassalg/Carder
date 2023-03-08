from collections import deque
from csv import reader
from math import floor
from pathlib import Path

import unidecode
import toml

from PIL import Image, ImageOps, ImageDraw, ImageFont

from carder.errors import TemplatePartValueError
from carder.utils import mm2px, rect2size, rect2pos
from carder.PIL import fit_text_to_rect

A4_SIZE = (2480, 3508)  # px
SUPPORTED_IMAGES_EXTENSIONS = (".png", ".jpg")
DEFAULT_FONT = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", 40)


# Templating


def get_cards_data(
    template_data: dict, template_path: Path, resolution: int, locale: str
) -> dict:
    """Take the template parts and return a dict of cards data, sorted by card id"""
    assert "card" not in template_data, "Metadata found in template data"

    def get_image(path: Path, size: tuple) -> Image.Image:
        """Get an image from a path, resize it and remove transparency

        Mostly for pdf use
        """
        image = Image.open(path)
        resized_image = image.resize(size)
        resized_image.info["transparency"] = 255
        return resized_image

    def get_font(template_part: dict, template_dir: Path) -> dict:
        """Return the font for the part"""
        try:
            return ImageFont.truetype(str(template_dir / template_part["font"]), 40)
        except KeyError:
            return DEFAULT_FONT

    def unfold_image(path: Path) -> dict:
        """
        Unfold image data

        Return a path for each card_id
        """
        result = {}

        if not path.exists() or not path.is_dir():
            return result

        for image_path in path.rglob("*"):  # Probably enhance the pattern here
            card_id = image_path.stem.lower()
            result[card_id] = image_path

        return result

    def unfold_text(path: Path, locale: str = "", to_ascii: bool = False) -> dict:
        """
        Unfold text data

        Return a string for each card_id according to the supplied locale

        If no locale was supplied, takes the first row from the csv
        """
        result = {}

        with path.open() as csv_data:
            csv_reader = reader(csv_data)
            locale_idx = 1

            if locale:
                try:
                    locales = {
                        locale: idx
                        for idx, locale in enumerate(next(csv_reader))
                        if idx > 0
                    }
                    locale_idx = locales[locale]
                except IndexError as error:
                    error.add_note(
                        f"invalid locale {locale} " f"among {locales.keys()} on {path}"
                    )
                    raise

            for row in csv_reader:
                # data = _get_base_data(template_part)
                card_id = row[0]
                text = row[locale_idx]

                if to_ascii:
                    # Sometimes your font doesn't take utf-8
                    text = unidecode.unidecode(text)

                result[card_id] = text

        return result

    template_dir = template_path.parent

    # Start by sorting the content to apply defaults last
    sorted_content = deque()
    for name, data in template_data.items():
        try:
            path = Path(data["path"])
        except KeyError:
            raise TemplatePartValueError(f"Malformed template part {name}: no path")

        if ".png" in path.suffixes:
            # This is a default, to be applied to every card
            sorted_content.append((name, data))
        else:
            sorted_content.appendleft((name, data))

    # For each template part, assign the relevant data
    cards_data = {}

    for name, data in sorted_content:
        path = template_dir / Path(data["path"])
        rect = mm2px(data["rect"], dpi=resolution)
        size = rect2size(rect)

        if ".csv" in path.suffixes:
            # Text data
            text_by_id = unfold_text(path, locale, to_ascii=data.get("to_ascii", False))
            font = get_font(data, template_dir)

            for card_id, text in text_by_id.items():
                cards_data.setdefault(card_id, {}).update(
                    {
                        name: {
                            "rect": rect,
                            "font": font,
                            "text": fit_text_to_rect(text, font, rect),
                        }
                    }
                )
        elif ".png" in path.suffixes:
            # Default image data
            # This should happen last and be applied to all cards
            for data in cards_data.values():
                data[name] = {"rect": rect, "image": get_image(path, size)}
        elif path.is_dir():
            # Image data
            img_path_by_id = unfold_image(path)
            for card_id, img_path in img_path_by_id.items():
                cards_data.setdefault(card_id, {}).update(
                    {name: {"rect": rect, "image": get_image(img_path, size)}}
                )
        else:
            raise TemplatePartValueError(
                f"template part {name} path cannot be processed"
            )

    return cards_data


def make_cards(cards_data: dict, card_bg: Image.Image) -> list:
    """Get all cards in a list of list, each sublist representing a page"""
    # Fill card background with the template data for each card
    cards = []
    for card_id, card_data in cards_data.items():
        bg = card_bg.copy()

        for name, part_data in card_data.items():
            pos = rect2pos(part_data["rect"])
            if "image" in part_data:
                bg.paste(part_data["image"], pos)
            elif "text" in part_data:
                image_draw = ImageDraw.Draw(bg)
                image_draw.multiline_text(
                    part_data["rect"], part_data["text"], font=part_data["font"], fill=0
                )
            else:
                raise TemplatePartValueError(
                    f"Unknown part type for {name}:{part_data}"
                )

        cards.append(bg)

    return cards


def make_card_background(metadata: dict):
    """Make the card background image"""
    resolution = metadata["resolution"]
    card_size = rect2size(mm2px(metadata["rect"], dpi=resolution))
    border_data = metadata.get("border", {})
    border_size = mm2px(border_data.get("size", 0), dpi=resolution)

    border_color = border_data.get("color", 0)
    try:
        border_color = tuple(border_color)
    except TypeError:  # Single int
        border_color = (border_color, border_color, border_color)

    card_bg = Image.new(
        mode="RGB", size=card_size, color=tuple(metadata.get("background_color", 255))
    )
    ## Set the border
    card_bg = ImageOps.expand(card_bg, border=border_size, fill=border_color)
    return card_bg


def make_pdf(cards: list, resolution: int, out_path: Path, repeat: int = 1):
    """Get the cards splitted per pages"""
    card_width = cards[0].width
    card_height = cards[0].height

    n_horizontal = floor(A4_SIZE[0] / card_width)
    n_vertical = floor(A4_SIZE[1] / card_height)
    n_pages = n_horizontal * n_vertical

    pages = []
    cards *= repeat

    for idx, card in enumerate(cards):
        y = idx % n_pages // n_vertical
        x = idx % n_horizontal

        if not idx % n_pages:
            pages.append(Image.new("RGB", A4_SIZE, (255, 255, 255)))

        pages[-1].paste(card, (card_width * x, card_height * y))

    pages[0].save(
        out_path, save_all=True, append_images=pages[1:], resolution=resolution
    )
    return pages


def main(template_path: Path, output: Path, locale: str, repeat: int = 1):
    """Get a template in a .toml format and create cards from it

    A template should look like the following:

    [card]
    rect: [0, 0, width, height] # mm
    background_color: [r, g, b]
    resolution: int # DPI

    [card.border] # optional
    size: float # mm
    color: [r, g, b]

    [my_custom_text_property]
    path: my_translation_file.csv
    rect: [pos_x, pos_y, width, height] # mm
    font: my_font_path # optional

    [my_custom_templated_image_property]
    path: my_images_folder_path/
    rect: [pos_x, pos_y, width, height] # mm

    [my_custom_fixed_image]
    path: my_image_path.png
    rect: [pos_x, pos_y, width, height] # mm

    Texts and templated images are unfolded from .csv files and folders

    csv data should be formatted either like

    |     id    |    locale_1   |    locale_2   |
    |-----------|---------------|---------------|
    | card_id_1 | text_card1_l1 | text_card1_l2 |
    | card_id_2 | text_card2_l1 | text_card2_l2 |

    or

    # no header
    | card_id_1 | text_card1_l1 |
    | card_id_2 | text_card2_l1 |

    Images in an image folder should be named after their card_id

    The program will then output a PDF with the templated cards
    """
    # Get data from template
    with template_path.open("r") as template_file:
        full_data = toml.load(template_file)
    template_data = full_data.copy()

    # Extract metadata
    metadata = template_data.pop("card")
    resolution = metadata["resolution"]

    # Get card data per card_id
    cards_data = get_cards_data(template_data, template_path, resolution, locale)

    # Create the card background
    card_bg = make_card_background(metadata)

    # Makes cards images
    cards = make_cards(cards_data, card_bg)

    # Save a pdf out of that
    make_pdf(cards, resolution, output, repeat)
