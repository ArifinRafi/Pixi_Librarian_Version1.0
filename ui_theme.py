# Look and feel for the Pixi control panel.
#
# Everything here is plain Tkinter - the Raspberry Pi image only ships with
# the standard library, so we draw the "modern" bits (rounded buttons, cards,
# pills) on a Canvas by hand instead of pulling in a widget toolkit.

import tkinter as tk
import tkinter.font as tkfont

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG = '#12151c'          # window background
SURFACE = '#1b2029'     # cards
SURFACE_HI = '#232a35'  # hovered cards
BORDER = '#2c3441'

TEXT = '#e8ecf3'
TEXT_DIM = '#8b95a6'

ACCENT = '#3ea6ff'      # librarian / primary
ACCENT_DARK = '#2b7fc4'
GREEN = '#35c98a'       # general mode / connected
AMBER = '#f0a23c'       # manual mode
RED = '#e0554f'         # stop / disconnected

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
# Bengali needs a font that actually has the glyphs.  Raspbian ships Noto,
# Windows has Nirmala UI, so we try a few and fall back to the default.
BENGALI_CANDIDATES = ['Noto Sans Bengali', 'Nirmala UI', 'Vrinda', 'FreeSans']
LATIN_CANDIDATES = ['Segoe UI', 'DejaVu Sans', 'Helvetica']

_fonts = {}


def _pick(root, candidates, fallback):
    available = set(tkfont.families(root))
    for name in candidates:
        if name in available:
            return name
    return fallback


def init_fonts(root):
    """Work out which font families exist on this machine. Call once."""
    latin = _pick(root, LATIN_CANDIDATES, 'TkDefaultFont')
    bengali = _pick(root, BENGALI_CANDIDATES, latin)

    _fonts['title'] = tkfont.Font(root=root, family=latin, size=30, weight='bold')
    _fonts['heading'] = tkfont.Font(root=root, family=latin, size=19, weight='bold')
    _fonts['subheading'] = tkfont.Font(root=root, family=latin, size=13)
    _fonts['body'] = tkfont.Font(root=root, family=latin, size=12)
    _fonts['small'] = tkfont.Font(root=root, family=latin, size=10)
    _fonts['mono'] = tkfont.Font(root=root, family='Courier', size=10)

    # Bengali reads badly at small sizes, so bump it up a little
    _fonts['bengali'] = tkfont.Font(root=root, family=bengali, size=16)
    _fonts['bengali_big'] = tkfont.Font(root=root, family=bengali, size=22)


def font(name):
    return _fonts.get(name, _fonts.get('body'))


def speech_font(language):
    """Pick a font that can render the language we are answering in."""
    if language == 'bn':
        return _fonts.get('bengali')
    return _fonts.get('subheading')


# ---------------------------------------------------------------------------
# Rounded rectangle helper
# ---------------------------------------------------------------------------
def round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """Draw a rounded rectangle on a canvas and return the polygon id."""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


# ---------------------------------------------------------------------------
# Rounded button
# ---------------------------------------------------------------------------
class RoundedButton(tk.Canvas):
    """A flat, rounded button.  tk.Button cannot be styled this way on Linux."""

    def __init__(self, master, text, command=None, width=200, height=48,
                 fill=ACCENT, hover=ACCENT_DARK, text_color='#ffffff',
                 font_name='body', radius=14, **kwargs):
        tk.Canvas.__init__(self, master, width=width, height=height,
                           highlightthickness=0, bd=0,
                           bg=kwargs.pop('bg', SURFACE))
        self.command = command
        self.fill = fill
        self.hover = hover
        self.enabled = True

        self.shape = round_rect(self, 1, 1, width - 1, height - 1, radius,
                                fill=fill, outline='')
        self.label = self.create_text(width // 2, height // 2, text=text,
                                      fill=text_color, font=font(font_name))

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)

    def _on_enter(self, event):
        if self.enabled:
            self.itemconfig(self.shape, fill=self.hover)

    def _on_leave(self, event):
        if self.enabled:
            self.itemconfig(self.shape, fill=self.fill)

    def _on_click(self, event):
        if self.enabled and self.command:
            self.command()

    def set_text(self, text):
        self.itemconfig(self.label, text=text)

    def set_fill(self, fill, hover=None):
        self.fill = fill
        self.hover = hover or fill
        self.itemconfig(self.shape, fill=fill)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.itemconfig(self.shape, fill=self.fill if enabled else BORDER)


# ---------------------------------------------------------------------------
# Card - a rounded panel used on the mode selector screen
# ---------------------------------------------------------------------------
class ModeCard(tk.Canvas):

    def __init__(self, master, title, subtitle, accent, command=None,
                 width=280, height=300):
        tk.Canvas.__init__(self, master, width=width, height=height,
                           highlightthickness=0, bd=0, bg=BG)
        self.command = command
        self.accent = accent

        self.body = round_rect(self, 2, 2, width - 2, height - 2, 22,
                               fill=SURFACE, outline=BORDER)
        # A coloured bar across the top of the card
        self.stripe = round_rect(self, 2, 2, width - 2, 70, 22, fill=accent,
                                 outline='')
        self.create_rectangle(2, 48, width - 2, 70, fill=accent, outline='')

        self.create_text(width // 2, 36, text=title, fill='#0d1117',
                         font=font('heading'))
        self.create_text(width // 2, 130, text=subtitle, fill=TEXT_DIM,
                         font=font('body'), width=width - 60, justify='center')

        self.dot = self.create_oval(width // 2 - 26, height - 106,
                                    width // 2 + 26, height - 54,
                                    fill=accent, outline='')
        self.create_text(width // 2, height - 32, text='TAP TO ENTER',
                         fill=TEXT_DIM, font=font('small'))

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)

    def _on_enter(self, event):
        self.itemconfig(self.body, fill=SURFACE_HI, outline=self.accent)

    def _on_leave(self, event):
        self.itemconfig(self.body, fill=SURFACE, outline=BORDER)

    def _on_click(self, event):
        if self.command:
            self.command()


# ---------------------------------------------------------------------------
# Status pill - small coloured badge, used for the Arduino link and mic state
# ---------------------------------------------------------------------------
class StatusPill(tk.Canvas):

    def __init__(self, master, text='', color=TEXT_DIM, width=190, height=30,
                 bg=BG):
        tk.Canvas.__init__(self, master, width=width, height=height,
                           highlightthickness=0, bd=0, bg=bg)
        self.shape = round_rect(self, 1, 1, width - 1, height - 1, height // 2,
                                fill=SURFACE, outline=BORDER)
        self.dot = self.create_oval(12, height // 2 - 4, 20, height // 2 + 4,
                                    fill=color, outline='')
        self.label = self.create_text(30, height // 2, text=text, fill=TEXT_DIM,
                                      font=font('small'), anchor='w')

    def set(self, text, color):
        self.itemconfig(self.label, text=text)
        self.itemconfig(self.dot, fill=color)
