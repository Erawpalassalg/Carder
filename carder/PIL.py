from PIL.ImageFont import ImageFont

from carder.utils import rect2size


def fit_text_to_rect(text: str, font: ImageFont, rect: tuple) -> str:
    """Given a rect and a font, return a string which will make the text fir the rect"""
    text = text.replace("\n", " ").strip()  # Normalize text
    remaining_words = text.split(" ")
    sentences = []
    box_size = rect2size(rect)

    n = len(remaining_words)
    while remaining_words:
        sentence = " ".join(remaining_words[:n])
        # If the sentence is more than 1 word and too long, shorten it
        if n > 1 and font.getlength(sentence) > box_size[0]:
            n -= 1
            continue

        # Otherwise, just add it and go to the next part
        sentences.append(sentence)
        remaining_words = remaining_words[n:]
        n = len(remaining_words)

    return "\n".join(sentences)
