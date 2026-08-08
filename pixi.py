# Pixi - Autonomous Humanoid Librarian Robot
# Control panel, Version 1.0
# Roboway Labs, Dhaka
#
# Everything runs inside one window.  The three modes are Frames that get
# raised in turn, rather than separate processes, so they can all share the
# one serial link to the Arduino - the port can only be opened once.
#
#   Librarian Mode  - Bengali / English, answers questions about the library
#   General Mode    - answers anything, using Wikipedia and Google
#   Manual Mode     - drive the base and the arms by gamepad or by voice

import sys
import tkinter as tk

import robot_link
import ui_theme as theme
from General_mode import GeneralMode
from Librarian import LibrarianMode
from Manual_mode import ManualMode

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800


class HomeScreen(tk.Frame):
    """The mode selector - three big cards, meant for the touchscreen."""

    def __init__(self, master, on_select, on_shutdown):
        tk.Frame.__init__(self, master, bg=theme.BG)

        tk.Label(self, text='PIXI', bg=theme.BG, fg=theme.TEXT,
                 font=theme.font('title')).pack(pady=(70, 0))
        tk.Label(self, text='AUTONOMOUS HUMANOID LIBRARIAN  -  VERSION 1.0',
                 bg=theme.BG, fg=theme.TEXT_DIM,
                 font=theme.font('small')).pack(pady=(4, 34))

        cards = tk.Frame(self, bg=theme.BG)
        cards.pack()

        theme.ModeCard(cards, 'LIBRARIAN',
                       'Ask where a book is.\nবাংলা and English.',
                       theme.ACCENT,
                       command=lambda: on_select('librarian')).pack(side='left', padx=14)

        theme.ModeCard(cards, 'GENERAL',
                       'Ask anything at all.\nWikipedia and the web.',
                       theme.GREEN,
                       command=lambda: on_select('general')).pack(side='left', padx=14)

        theme.ModeCard(cards, 'MANUAL',
                       'Drive the base and arms\nby gamepad or by voice.',
                       theme.AMBER,
                       command=lambda: on_select('manual')).pack(side='left', padx=14)

        theme.RoundedButton(self, 'SHUT DOWN', command=on_shutdown, width=180,
                            height=46, fill=theme.SURFACE, hover=theme.RED,
                            text_color=theme.TEXT_DIM, font_name='small',
                            bg=theme.BG).pack(pady=44)


class PixiApp(object):

    def __init__(self, root):
        self.root = root
        self.root.title('Pixi Control Panel')
        self.root.geometry('%dx%d' % (WINDOW_WIDTH, WINDOW_HEIGHT))
        self.root.configure(bg=theme.BG)
        self.root.protocol('WM_DELETE_WINDOW', self.quit)

        theme.init_fonts(self.root)

        self.container = tk.Frame(self.root, bg=theme.BG)
        self.container.pack(fill='both', expand=True)

        self.current = None
        self.frames = {
            'home': HomeScreen(self.container, self.show, self.quit),
            'librarian': LibrarianMode(self.container, on_back=self.go_home),
            'general': GeneralMode(self.container, on_back=self.go_home),
            'manual': ManualMode(self.container, on_back=self.go_home),
        }
        for frame in self.frames.values():
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # F11 toggles full screen - on the robot it starts full screen, on a
        # desk it is easier to work in a window.
        self.fullscreen = False
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', lambda event: self.go_home())

        self.show('home')

    # -- navigation ---------------------------------------------------------
    def show(self, name):
        frame = self.frames.get(name)
        if frame is None:
            return

        # Let the mode we are leaving tidy up - Manual Mode stops the motors
        if self.current is not None and self.current is not frame:
            leave = getattr(self.current, 'on_leave', None)
            if leave:
                leave()

        frame.tkraise()
        self.current = frame

        enter = getattr(frame, 'on_enter', None)
        if enter:
            enter()

    def go_home(self):
        self.show('home')

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes('-fullscreen', self.fullscreen)

    # -- shutdown -----------------------------------------------------------
    def quit(self):
        print('Shutting down Pixi.')
        if self.current is not None:
            leave = getattr(self.current, 'on_leave', None)
            if leave:
                leave()
        robot_link.link.stop()
        robot_link.link.disconnect()
        self.root.destroy()
        # speech and gamepad threads are daemons, but pyttsx3 sometimes hangs
        # on to the audio device, so make sure we really go away.
        sys.exit(0)


def check_tk(root):
    """Warn about the ancient Tk that ships with macOS.

    Apple still puts Tcl/Tk 8.5.9 from 2010 in /usr/lib, and any Python
    linked against it lays the window out correctly but paints nothing at
    all - you get an empty grey box.  Raspbian has 8.6, so this only ever
    bites on a Mac development machine.
    """
    patchlevel = root.tk.call('info', 'patchlevel')
    if root.tk.call('tk', 'windowingsystem') == 'aqua':
        if patchlevel.startswith('8.5'):
            print('=' * 68)
            print('WARNING: Tcl/Tk %s.  This is the deprecated Tk that Apple' % patchlevel)
            print('ships in /usr/lib, and it draws nothing on modern macOS.')
            print('The window will open completely blank.')
            print()
            print('Use a Python built against Tk 8.6 instead:')
            print('    brew install python-tk@3.12')
            print('    /opt/homebrew/bin/python3.12 -m venv .venv')
            print('    .venv/bin/pip install -r requirements.txt')
            print('=' * 68)
    return patchlevel


def main():
    root = tk.Tk()
    check_tk(root)
    PixiApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
