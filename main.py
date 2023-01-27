import click
import textwrap

from csv import reader
from glob import glob
from itertools import tee
from math import ceil
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont

# For mm to pixel, see https://pixelcalculator.com/en
CARD_SIZE = (744, 1039) # px
A4_SIZE = (2480, 3508) # px
IMAGE_MARGIN = 59 # px
IMAGE_SIZE = (CARD_SIZE[0] - IMAGE_MARGIN * 2, 429)
IMAGE_LOCATION = (IMAGE_MARGIN, IMAGE_MARGIN * 2) # px
TEXT_MARGIN = 83 # px
RESOLUTION = 300 # DPI

@click.command()
@click.argument("images_folder", type=click.Path(exists=True))
@click.argument("text", type=click.File("r"))
@click.option("--locale", type=click.Choice(("en", "fr"), case_sensitive=False), default="en")
def run(images_folder, text, locale):
    csv_reader = reader(text)
    locales = {locale: idx for idx, locale in enumerate(next(csv_reader)) if idx > 0}
    locale_idx = locales[locale]

    data = {}
    for row in csv_reader:
        ref, place = row[0].split(" ")
        ref = ref.lower()

        data.setdefault(ref, {})[place] = row[locale_idx]

    for image_path in Path(images_folder).rglob("*.jpg"):
        ref = image_path.stem.lower()
        data.setdefault(ref, {})["image_path"] = image_path


    # Create a card_template and render it in PDF
    card_template = Image.new(mode="RGB", size=CARD_SIZE, color=(255, 255, 255))
    card_template = ImageOps.expand(card_template, border=1, fill=0)

    ## Gather all images
    # images = [card_template for _i in range(8*9)]

    # Make pages
    n_h = int(A4_SIZE[0] / CARD_SIZE[0])
    n_v = int(A4_SIZE[1] / CARD_SIZE[1])
    n = n_h * n_v

    pages = []
    x = 0
    y = 0

    for ref, values in data.items():
        if not x and not y:
            pages.append(Image.new("RGB", A4_SIZE, (255, 255, 255)))

        template = card_template.copy()

        # Put image on template
        try:
            image = Image.open(values["image_path"])
            image.load()
            resized_image = image.resize(IMAGE_SIZE)
        except KeyError:
            print(f"No image for {ref}")
            resized_image.new("RGB", IMAGE_SIZE, 125)
        finally:
            template.paste(resized_image, IMAGE_LOCATION)

        # Put name on template
        try:
            name = values["name"]
        except KeyError:
            print(f"No name for {ref}")
            name = ref
        finally:
            fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", 40)
            d = ImageDraw.Draw(template)
            d.text((TEXT_MARGIN, IMAGE_MARGIN * 2 + IMAGE_SIZE[1] + IMAGE_MARGIN), name.capitalize(), font=fnt, fill=0)

        # Put text on template
        try:
            text = values["text"]
        except KeyError:
            print(f"No text for {ref}")
        else:
            fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", 40)
            remaining_words = text.split(" ")
            sentences = []
            box_size = (CARD_SIZE[0] - TEXT_MARGIN * 2)

            while remaining_words:
                n = 4
                while True:
                    n = min(n, len(remaining_words))
                    if n == 0:
                        break
                    

                    sentence = " ".join(remaining_words[:n])
                    if fnt.getlength(sentence) > box_size:
                        n -= 1
                    elif fnt.getlength(" ".join(remaining_words[:n+1])) > box_size or n == len(remaining_words):
                        sentences.append(sentence)
                        remaining_words = remaining_words[n:]
                        break
                    else:
                        n += 1

            d = ImageDraw.Draw(template)
            d.multiline_text((TEXT_MARGIN, IMAGE_MARGIN * 2 + IMAGE_SIZE[1] + IMAGE_MARGIN + 40 + IMAGE_MARGIN), "\n".join(sentences), font=fnt, fill=0)

        
        # Build pages
        pages[-1].paste(template, (CARD_SIZE[0] * x, CARD_SIZE[1] * y))
        x += 1
        if x == n_h:
            x = 0
            y += 1
            if y == n_v:
                y = 0


    pages[0].save("pages_out.pdf", save_all=True, append_images=pages[1:], resolution=RESOLUTION)

if __name__ == "__main__":
    run()
