import click
import toml
import unidecode

from csv import reader
from glob import glob
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont

# For mm to pixel, see https://pixelcalculator.com/en
A4_SIZE = (2480, 3508) # px
INCH: float = 25.4 # mm
SUPPORTED_IMAGES_EXTENSIONS = (".png", ".jpg")

def mm2px(*args, dpi: float):
    """Return px from milimeters, according to DPI"""

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
    return (rect[2] - rect[0], rect[3] - rect[1])


def rect2pos(rect: tuple) -> tuple:
    return rect[:2]


@click.command()
@click.argument("template", type=click.Path(exists=True))
@click.argument("out", type=click.Path())
@click.option("--locale", type=click.Choice(("en", "fr"), case_sensitive=False), default="en")
@click.option("--repeat", type=int, default=1)
def run(template, out, locale, repeat):
    template_path = Path(template)
    with Path(template).open("r") as template_file:
        template_data = toml.load(template_file)

    # Extract the metadata for the template
    card_template_data = template_data.pop("card")
    card_border_data = template_data.pop("border")

    resolution = card_template_data["resolution"]
    card_rect = mm2px(card_template_data["rect"], dpi=resolution)
    card_size = rect2size(card_rect)

    card_max_border = 0

    # Create a card_template
    card_template = Image.new(mode="RGB", size=card_size, color=tuple(card_template_data.get("background_color", 0)))

    # Instantiate data
    cards_data = {}
    additional_card_data = {} # Generic, to be added to all cards data afterward

    # Extract border data
    try :
        border_data_file = template_path.parent / card_border_data["path"]
    except KeyError:
        additional_card_data["border"] = card_border_data
        additional_card_data["border"]["size"] = mm2px(additional_card_data["border"]["size"], dpi=resolution)
        card_max_border = card_border_data["size"]
    else:
        with border_data_file.open() as csv_data:
            csv_reader = reader(csv_data)
            next(csv_reader) # pass header
            for card_id, size, color in csv_reader:
                cards_data.setdefault(card_id, {})["border"] = {"size": mm2px(int(size), dpi=resolution), "color": color}
                card_max_border = max(card_max_border, cards_data[card_id]["border"]["size"])

    # Extract data from files
    for ref, data in template_data.items():
        # Instantiate border data

        try:
            path = template_path.parent / data["path"]
        except KeyError:
            print(f"No path for {ref}")


        try:
            rect = mm2px(data["rect"], dpi=resolution)
        except KeyError:
            print(f"No rect for {ref}")
        
        if path.is_dir():
            # An image folder
            for image_path in path.rglob("*"): # Probably enhance the pattern here
                card_id = image_path.stem.lower()
                cards_data.setdefault(card_id, {}).setdefault(ref, {"rect": rect})["image"] = image_path
        else:
            if path.suffixes[0] in SUPPORTED_IMAGES_EXTENSIONS:
                # A single image to generalize
                additional_card_data[ref] = {"rect": rect, "image": path}
            else:
                # A csv file path
                with path.open() as csv_data:
                    csv_reader = reader(csv_data)
                    try:
                        locales = {locale: idx for idx, locale in enumerate(next(csv_reader)) if idx > 0}
                    except UnicodeDecodeError:
                        print(f"decode failed on {path}")
                        raise
                    locale_idx = locales[locale]

                    for row in csv_reader:
                        card_id = row[0]
                        text = row[locale_idx]
                        if ref == "name":
                            text = unidecode.unidecode(text)
                        cards_data.setdefault(card_id, {}).setdefault(ref, {"rect": rect})["text"] = text

                        try:
                            cards_data[card_id][ref]["font"] = ImageFont.truetype(str(template_path.parent / data["font"]), 40)
                        except KeyError:
                            cards_data[card_id][ref]["font"] = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", 40)

    # Make pages
    n_h = int(A4_SIZE[0] / (card_size[0] + card_max_border * 2))
    n_v = int(A4_SIZE[1] / (card_size[1] + card_max_border * 2))
    n = n_h * n_v

    pages = []
    x = 0
    y = 0


    # Make Images
    for card_id in cards_data:
        # new_page if needed
        if not x and not y:
            pages.append(Image.new("RGB", A4_SIZE, (255, 255, 255)))

        card_id = card_id.lower()
        card_data = cards_data[card_id]
        template = card_template.copy()
        card_data.update(additional_card_data)

        template = ImageOps.expand(template, border=card_data["border"]["size"], fill=card_data["border"]["color"])


        for ref, values in card_data.items():
            # Put image on card
            try:
                image = Image.open(values["image"])
            except KeyError:
                pass
            else:
                image.load()
                try:
                    rect = values["rect"]
                except KeyError:
                    print(f"No rect defined for {card_id} {ref}")
                else:
                    size = rect2size(rect)
                    pos = rect2pos(rect)
                    resized_image = image.resize(size)
                    resized_image.info["transparency"] = 255
                    template.paste(resized_image, pos)

            # Put text on card
            try:
                text = values["text"]
            except KeyError:
                pass
            else:
                try:
                    rect = values["rect"]
                except KeyError:
                    print(f"No rect defined for {card_id} {ref}")
                else:
                    fnt = values["font"]
                    remaining_words = text.split(" ")
                    sentences = []
                    box_size = rect2size(rect)

                    while remaining_words:

                        # This is special to our game...
                        try:
                            n = remaining_words.index(";")
                            sentence = " ".join(remaining_words[:n])
                            if fnt.getlength(sentence) <= box_size[0]:
                                remaining_words = remaining_words[n+1:]
                                sentences.append(sentence)
                                sentences.append("---")
                                continue
                        except ValueError:
                            pass

                        try:
                            n = remaining_words.index(next(word for word in remaining_words if word.endswith(",")))
                            sentence = " ".join(remaining_words[:n+1])[:-1]
                            if fnt.getlength(sentence) <= box_size[0]:
                                remaining_words = remaining_words[n+1:]
                                sentences.append(sentence)
                                continue
                        except StopIteration:
                            pass

                        n = 4


                        while True:
                            n = min(n, len(remaining_words))
                            if n == 0:
                                break

                            sentence = " ".join(remaining_words[:n])
                            if fnt.getlength(sentence) > box_size[0]:
                                n -= 1
                            elif fnt.getlength(" ".join(remaining_words[:n+1])) > box_size[0] or n == len(remaining_words):
                                sentences.append(sentence)
                                remaining_words = remaining_words[n:]
                                break
                            else:
                                n += 1

                    d = ImageDraw.Draw(template)
                    d.multiline_text(rect, "\n".join(sentences), font=fnt, fill=0)

        # Build pages
        for _ in range(0, repeat):
            pages[-1].paste(template, ((card_size[0] + card_max_border * 2) * x, (card_size[1] + card_max_border * 2) * y))
            x += 1
            if x == n_h:
                x = 0
                y += 1
                if y == n_v:
                    y = 0

    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=resolution)

if __name__ == "__main__":
    run()
