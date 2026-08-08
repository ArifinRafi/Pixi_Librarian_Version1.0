# General Mode - Pixi answers ordinary questions.
#
# Whatever the visitor asks goes through the small talk table first, then
# Wikipedia, then Google.  The answer is shown on screen and read out loud.
# There is also a text box so somebody can type a question when the hall is
# too noisy for the microphone.

import json
import threading
import tkinter as tk

import config
import speech
import ui_theme as theme
import web_search


def load_responses(file_path):
    """Read general_responses.json.  Returns {} if it is missing."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except IOError:
        print("The file %s does not exist." % file_path)
        return {}
    except ValueError:
        print("Error decoding JSON from the file %s." % file_path)
        return {}


GREETINGS = [
    "Hello Boss. I am Pixi, your autonomous humanoid robot. How can I help?",
    "Hi Sir! I am Pixi. Please ask me your question.",
    "Hello, I am Pixi. How may I help you today?",
]


class GeneralMode(tk.Frame):

    def __init__(self, master, on_back=None):
        tk.Frame.__init__(self, master, bg=theme.BG)
        self.on_back = on_back
        self.busy = False

        data = load_responses(config.GENERAL_RESPONSES)
        self.keywords_responses = data.get('keywords_responses', {})
        print("Loaded %d small talk keywords" % len(self.keywords_responses))

        self._build()

    # -- layout -------------------------------------------------------------
    def _build(self):
        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill='x', padx=30, pady=(22, 6))

        theme.RoundedButton(header, '<  BACK', command=self._go_back,
                            width=110, height=38, fill=theme.SURFACE,
                            hover=theme.SURFACE_HI, text_color=theme.TEXT,
                            font_name='small', bg=theme.BG).pack(side='left')

        tk.Label(header, text='GENERAL MODE', bg=theme.BG, fg=theme.GREEN,
                 font=theme.font('heading')).pack(side='left', padx=20)

        self.status_pill = theme.StatusPill(header, 'Ready', theme.TEXT_DIM,
                                            width=260)
        self.status_pill.pack(side='right')

        tk.Label(self, text='Ask me anything - I will look it up on '
                            'Wikipedia and the web',
                 bg=theme.BG, fg=theme.TEXT_DIM,
                 font=theme.font('body')).pack(pady=(14, 12))

        # -- ask ------------------------------------------------------------
        controls = tk.Frame(self, bg=theme.BG)
        controls.pack()

        self.ask_button = theme.RoundedButton(
            controls, 'ASK  ●  SPEAK NOW', command=self.start_listening,
            width=320, height=68, fill=theme.GREEN, hover='#2aa06e',
            font_name='heading', bg=theme.BG, radius=20)
        self.ask_button.pack(side='left', padx=8)

        # Typed fallback for when the microphone cannot cope with the room
        typed = tk.Frame(self, bg=theme.BG)
        typed.pack(pady=(16, 4))

        self.entry = tk.Entry(typed, width=48, font=theme.font('body'),
                              bg=theme.SURFACE, fg=theme.TEXT,
                              insertbackground=theme.TEXT, relief='flat',
                              highlightthickness=1,
                              highlightbackground=theme.BORDER,
                              highlightcolor=theme.GREEN)
        self.entry.pack(side='left', ipady=9, padx=(0, 8))
        self.entry.bind('<Return>', lambda event: self.ask_typed())

        theme.RoundedButton(typed, 'SEND', command=self.ask_typed, width=100,
                            height=40, fill=theme.SURFACE_HI,
                            hover=theme.BORDER, text_color=theme.TEXT,
                            font_name='small', bg=theme.BG).pack(side='left')

        # -- transcript -----------------------------------------------------
        panels = tk.Frame(self, bg=theme.BG)
        panels.pack(fill='both', expand=True, padx=40, pady=(20, 30))

        self.you_label = self._panel(panels, 'You asked', theme.TEXT_DIM)
        self.pixi_label = self._panel(panels, 'Pixi says', theme.GREEN)

        self.source_label = tk.Label(self, text='', bg=theme.BG,
                                     fg=theme.TEXT_DIM,
                                     font=theme.font('small'))
        self.source_label.pack(pady=(0, 16))

    def _panel(self, parent, title, color):
        card = tk.Frame(parent, bg=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.BORDER)
        card.pack(fill='both', expand=True, pady=7)

        tk.Label(card, text=title.upper(), bg=theme.SURFACE, fg=color,
                 font=theme.font('small'), anchor='w').pack(fill='x', padx=18,
                                                            pady=(12, 2))
        body = tk.Label(card, text='---', bg=theme.SURFACE, fg=theme.TEXT,
                        font=theme.font('subheading'), anchor='w',
                        justify='left', wraplength=900)
        body.pack(fill='both', expand=True, padx=18, pady=(0, 14))
        return body

    # -- asking -------------------------------------------------------------
    def start_listening(self):
        if self.busy:
            return
        self._set_busy(True, 'Listening', theme.AMBER)
        self.you_label.config(text='...')
        self.pixi_label.config(text='...')
        self.source_label.config(text='')

        thread = threading.Thread(target=self._listen_worker)
        thread.daemon = True
        thread.start()

    def ask_typed(self):
        if self.busy:
            return
        question = self.entry.get().strip()
        if not question:
            return
        self.entry.delete(0, 'end')
        self._set_busy(True, 'Searching', theme.ACCENT)
        self.you_label.config(text=question)
        self.pixi_label.config(text='...')
        self._answer_in_background(question)

    def _listen_worker(self):
        text, error = speech.listen(config.LANG_ENGLISH)
        if error:
            self.after(0, self._show_error, error)
            return
        self.after(0, self.you_label.config, {'text': text})
        self.after(0, self.status_pill.set, 'Searching', theme.ACCENT)
        self._do_answer(text)

    def _answer_in_background(self, question):
        thread = threading.Thread(target=self._do_answer, args=(question,))
        thread.daemon = True
        thread.start()

    def _do_answer(self, question):
        reply, source = web_search.answer(question, self.keywords_responses)
        self.after(0, self._show_answer, reply, source)
        speech.speak(reply, config.LANG_ENGLISH)
        self.after(0, self._set_busy, False, 'Ready', theme.TEXT_DIM)

    def _show_answer(self, reply, source):
        self.pixi_label.config(text=reply)
        self.source_label.config(text='Source: %s' % source)
        self.status_pill.set('Speaking', theme.GREEN)

    def _show_error(self, error):
        self.pixi_label.config(text=error)
        self._set_busy(False, error[:34], theme.RED)

    def _set_busy(self, busy, status, color):
        self.busy = busy
        self.ask_button.set_enabled(not busy)
        self.status_pill.set(status, color)

    # -- housekeeping -------------------------------------------------------
    def on_leave(self):
        pass

    def _go_back(self):
        if self.busy:
            return
        if self.on_back:
            self.on_back()


if __name__ == '__main__':
    root = tk.Tk()
    root.title('Pixi - General Mode')
    root.geometry('1200x800')
    root.configure(bg=theme.BG)
    theme.init_fonts(root)
    GeneralMode(root).pack(fill='both', expand=True)
    root.mainloop()
