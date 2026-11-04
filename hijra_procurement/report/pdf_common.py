"""Drawing helpers shared by the HIJRA procurement documents (plain reportlab, no Odoo).

Positions are written top-down in points, like the paper templates.
"""
import base64
import logging
import os
from io import BytesIO

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_logger = logging.getLogger(__name__)

SANS, SANS_BOLD = 'HP-Sans', 'HP-Sans-Bold'
FONT_FILES = {SANS: 'Carlito-Regular.ttf', SANS_BOLD: 'Carlito-Bold.ttf'}
GREEN = (25 / 255.0, 107 / 255.0, 36 / 255.0)
GREY_BAND = (242 / 255.0, 242 / 255.0, 242 / 255.0)
A4_W, A4_H = 595.2756, 841.8898


def register_fonts(font_dir):
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in FONT_FILES.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, os.path.join(font_dir, filename)))


def text_width(text, font, size):
    return pdfmetrics.stringWidth(str(text or ''), font, size)


def wrap(text, font, width, size):
    lines = []
    for paragraph in str(text or '').split('\n'):
        current = ''
        for word in paragraph.split(' '):
            candidate = f'{current} {word}' if current else word
            if text_width(candidate, font, size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while text_width(word, font, size) > width and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and text_width(word[:cut], font, size) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines or ['']


def load_image(*candidates):
    """First candidate (raw bytes or base64) that PIL can read, as an ImageReader."""
    from PIL import Image
    for value in candidates:
        if not value:
            continue
        raw_value = value.encode() if isinstance(value, str) else bytes(value)
        options = [raw_value]
        try:
            options.append(base64.b64decode(raw_value))
        except Exception:
            pass
        for raw in options:
            try:
                image = Image.open(BytesIO(raw))
                image.load()
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGBA')
                buffer = BytesIO()
                image.save(buffer, format='PNG')
                buffer.seek(0)
                return ImageReader(buffer)
            except Exception:
                continue
        _logger.warning("Procurement PDF: could not read an image (%d bytes)", len(value))
    return None


def fmt_date(value):
    return value.strftime('%d %B %Y').lstrip('0') if value else ''


def fmt_short_date(value):
    return value.strftime('%d/%m/%Y') if value else ''


def fmt_amount(value):
    return f'{value:,.2f}'


class Page:
    """A canvas with top-down drawing helpers."""

    def __init__(self, canv, width, height, margin):
        self.c = canv
        self.w, self.h = width, height
        self.margin = margin

    def _y(self, y):
        return self.h - y

    def text(self, x, baseline, value, font=SANS, size=10.5, color=(0, 0, 0), align='left'):
        if value in (None, False, ''):
            return
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*color)
        draw = {'left': self.c.drawString, 'right': self.c.drawRightString,
                'center': self.c.drawCentredString}[align]
        draw(x, self._y(baseline), str(value))
        self.c.setFillGray(0)

    def line(self, x0, y0, x1, y1, width=0.5, gray=0.0):
        self.c.setLineWidth(width)
        self.c.setStrokeGray(gray)
        self.c.line(x0, self._y(y0), x1, self._y(y1))
        self.c.setStrokeGray(0)

    def rect(self, x0, y0, x1, y1, fill=None, stroke=True, width=0.5):
        self.c.setLineWidth(width)
        if fill is not None:
            self.c.setFillColorRGB(*fill)
        self.c.rect(x0, self._y(y1), x1 - x0, y1 - y0, stroke=1 if stroke else 0, fill=1 if fill else 0)
        self.c.setFillGray(0)

    def paragraph(self, x, top, width, text, font=SANS, size=10.5, leading=None, color=(0, 0, 0)):
        """Draw wrapped text from `top`; returns the y below it."""
        leading = leading or size * 1.28
        y = top
        for line in wrap(text, font, width, size):
            self.text(x, y + size, line, font, size, color)
            y += leading
        return y

    def image(self, value, box, align='left', valign='top'):
        """Fit an image (bytes/base64, or a list of candidates) inside box = (x0, y0, x1, y1)."""
        reader = load_image(*(value if isinstance(value, (list, tuple)) else [value]))
        if not reader:
            return False
        x0, y0, x1, y1 = box
        width, height = reader.getSize()
        scale = min((x1 - x0) / width, (y1 - y0) / height)
        w, h = width * scale, height * scale
        x = x0 if align == 'left' else (x1 - w if align == 'right' else x0 + (x1 - x0 - w) / 2.0)
        y = y0 if valign == 'top' else (y1 - h if valign == 'bottom' else y0 + (y1 - y0 - h) / 2.0)
        self.c.drawImage(reader, x, self._y(y + h), w, h, mask='auto')
        return True

    def logo(self, data, right=None, top=None, box=(110, 56)):
        if not data.get('logo'):
            return
        right = right if right is not None else self.w - self.margin
        top = top if top is not None else self.margin - 6
        self.image(data['logo'], (right - box[0], top, right, top + box[1]), align='right')
