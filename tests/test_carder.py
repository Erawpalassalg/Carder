import toml
from PIL import Image, ImageFont

from carder.carder import get_cards_data, make_card_background, make_cards, make_pdf
from carder.utils import rect2size, mm2px
from tests.utils import custom_test_dir, make_csv, RESOLUTION


def test_end_to_end():
    with custom_test_dir() as test_dir:
        image_dir = test_dir / "imgs/"
        template_path = test_dir / "template.toml"
        text_path = test_dir / "texts.csv"
        logo_path = test_dir / "logo.png"

        card_1_id = "card_1"
        card_2_id = "card_2"

        template_data = {
            "card": {
                "rect": [0, 0, 63, 88],
                "background_color": [255, 255, 255],
                "resolution": 300,
                "border": {"size": 0.2, "color": [0, 0, 0]},
            },
            "image": {"path": image_dir.name, "rect": [1, 1, 51, 87]},
            "text": {"path": text_path.name, "rect": [1, 1, 10, 10]},
            "logo": {"path": logo_path.name, "rect": [52, 1, 62, 87]},
        }

        # texts
        card_1_text = "stuff"
        card_2_text = "stufftoo"
        texts_data = (("id", "en"), (card_1_id, card_1_text), (card_2_id, card_2_text))

        with template_path.open("w") as template_file:
            toml.dump(template_data, template_file)

        make_csv(texts_data, text_path)

        # Make logo
        size = rect2size(template_data["logo"]["rect"])
        img = Image.new("RGB", size, color="red")
        img.save(logo_path)

        # Make images
        image_dir.mkdir(parents=True)

        for card_id in (card_1_id, card_2_id):
            image_path = image_dir / f"{card_id}.png"
            size = rect2size(template_data["image"]["rect"])
            img = Image.new("RGB", size, color="blue")
            img.save(image_path)

        locale = "en"
        metadata = template_data.pop("card")
        cards_data = get_cards_data(template_data, template_path, RESOLUTION, locale)
        # Test the data splitting
        assert isinstance(cards_data[card_1_id]["image"]["image"], Image.Image)
        assert isinstance(cards_data[card_2_id]["image"]["image"], Image.Image)
        assert isinstance(cards_data[card_1_id]["text"]["font"], ImageFont.FreeTypeFont)
        assert isinstance(cards_data[card_2_id]["text"]["font"], ImageFont.FreeTypeFont)
        assert cards_data[card_1_id]["text"]["text"] == card_1_text
        assert cards_data[card_2_id]["text"]["text"] == card_2_text
        assert isinstance(cards_data[card_1_id]["logo"]["image"], Image.Image)
        assert isinstance(cards_data[card_2_id]["logo"]["image"], Image.Image)
        assert cards_data[card_1_id]["image"]["rect"] == mm2px(
            template_data["image"]["rect"], dpi=RESOLUTION
        )
        assert (
            cards_data[card_1_id]["image"]["rect"]
            == cards_data[card_2_id]["image"]["rect"]
        )

        # Test the card background
        card_bg = make_card_background(metadata)
        assert (
            card_bg.width
            == mm2px(rect2size(metadata["rect"])[0], dpi=RESOLUTION)
            + mm2px(metadata["border"]["size"], dpi=RESOLUTION) * 2
        )
        assert (
            card_bg.height
            == mm2px(rect2size(metadata["rect"])[1], dpi=RESOLUTION)
            + mm2px(metadata["border"]["size"], dpi=RESOLUTION) * 2
        )

        assert card_bg.getpixel((0, 0)) == (0, 0, 0)
        assert card_bg.getpixel((card_bg.width / 2.0, card_bg.height / 2.0)) == (
            255,
            255,
            255,
        )

        # Test the cards number
        cards = make_cards(cards_data, card_bg)
        assert len(cards) == 2

        # Test the page output
        output_path = test_dir / "out.pdf"

        # Pages is a list of images, but it saves a pdf
        pages = make_pdf(cards, RESOLUTION, output_path)

        assert len(pages) == 1
        assert pages[0].getpixel((0, 0)) == (0, 0, 0)
        assert pages[0].getpixel((card_bg.width / 2.0, card_bg.height / 2.0)) == (
            0,
            0,
            255,
        )
        assert pages[0].getpixel((card_bg.width * 1.5, card_bg.height / 2.0)) == (
            0,
            0,
            255,
        )
        assert pages[0].getpixel((card_bg.width * 2.5, card_bg.height / 2.0)) == (
            255,
            255,
            255,
        )

        assert output_path.exists()

        # Try with a lot more cards
        pages = make_pdf(cards, RESOLUTION, output_path, repeat=9)

        assert len(pages) == 2

        for page in pages:
            assert page.getpixel((0, 0)) == (0, 0, 0)
            assert page.getpixel((card_bg.width / 2.0, card_bg.height / 2.0)) == (
                0,
                0,
                255,
            )
            assert page.getpixel((card_bg.width * 1.5, card_bg.height / 2.0)) == (
                0,
                0,
                255,
            )
            assert page.getpixel((card_bg.width * 2.5, card_bg.height / 2.0)) == (
                0,
                0,
                255,
            )

        assert output_path.exists()
