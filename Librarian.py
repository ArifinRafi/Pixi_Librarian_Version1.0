# Librarian Mode - Pixi answers questions about the library.
#
# The visitor picks a language, presses START, asks where a book is, and Pixi
# reads the shelf location back out loud.  The answers live in responses.json
# (Bengali) and responses_en.json (English) so the library staff can edit them
# without touching any code.

import json
import threading
import tkinter as tk

import config
import speech
import ui_theme as theme


# ---------------------------------------------------------------------------
# Response files
# ---------------------------------------------------------------------------
def load_responses(file_path):
    """Read one of the question/answer files.  Returns {} if it is missing."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except IOError:
        print("The file %s does not exist." % file_path)
        return {}
    except ValueError:
        print("Error decoding JSON from the file %s." % file_path)
        return {}


def generate_response(input_text, responses, language):
    """Find the first stored question that appears in what the visitor said."""
    print("Generating response for: %s" % input_text)
    text = input_text.lower()
    for question, response in responses.items():
        if question.lower() in text:
            print("Found matching response: %s" % response)
            return response

    if language == config.LANG_BENGALI:
        return "দুঃখিত, আমি আপনার প্রশ্নের উত্তর জানি না।"
    return "Sorry, I do not know the answer to that question."


# Prompts shown on screen, per language
STRINGS = {
    config.LANG_BENGALI: {
        'idle': 'শুরু করতে START চাপুন',
        'listening': 'শুনছি... এখন আপনার প্রশ্ন বলুন',
        'thinking': 'একটু অপেক্ষা করুন...',
        'speaking': 'উত্তর দিচ্ছি...',
        'you_said': 'আপনি বলেছেন',
        'pixi_said': 'পিক্সি বলছে',
        'start': 'START  ●  শুরু',
    },
    config.LANG_ENGLISH: {
        'idle': 'Press START and ask your question',
        'listening': 'Listening... please ask your question now',
        'thinking': 'One moment please...',
        'speaking': 'Answering...',
        'you_said': 'You said',
        'pixi_said': 'Pixi says',
        'start': 'START  ●  ASK PIXI',
    },
}


class LibrarianMode(tk.Frame):

    def __init__(self, master, on_back=None):
        tk.Frame.__init__(self, master, bg=theme.BG)
        self.on_back = on_back
        self.language = config.LANG_BENGALI
        self.busy = False

        # Both files are loaded up front - they are tiny and it means a
        # language switch is instant.
        self.responses = {}
        for lang, path in config.LIBRARIAN_RESPONSES.items():
            self.responses[lang] = load_responses(path)
            print("Loaded %d %s responses" % (len(self.responses[lang]), lang))

        self._build()
        self._apply_language()

    # -- layout -------------------------------------------------------------
    def _build(self):
        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill='x', padx=30, pady=(22, 6))

        back = theme.RoundedButton(header, '<  BACK', command=self._go_back,
                                   width=110, height=38, fill=theme.SURFACE,
                                   hover=theme.SURFACE_HI, text_color=theme.TEXT,
                                   font_name='small', bg=theme.BG)
        back.pack(side='left')

        tk.Label(header, text='LIBRARIAN MODE', bg=theme.BG, fg=theme.ACCENT,
                 font=theme.font('heading')).pack(side='left', padx=20)

        self.status_pill = theme.StatusPill(header, 'Ready', theme.TEXT_DIM,
                                            width=260)
        self.status_pill.pack(side='right')

        # -- language selector ---------------------------------------------
        picker = tk.Frame(self, bg=theme.BG)
        picker.pack(pady=(18, 8))

        tk.Label(picker, text='LANGUAGE', bg=theme.BG, fg=theme.TEXT_DIM,
                 font=theme.font('small')).pack(pady=(0, 8))

        buttons = tk.Frame(picker, bg=theme.BG)
        buttons.pack()

        self.bn_button = theme.RoundedButton(
            buttons, 'বাংলা', command=lambda: self.set_language(config.LANG_BENGALI),
            width=190, height=54, font_name='bengali', bg=theme.BG)
        self.bn_button.pack(side='left', padx=8)

        self.en_button = theme.RoundedButton(
            buttons, 'English', command=lambda: self.set_language(config.LANG_ENGLISH),
            width=190, height=54, font_name='subheading', bg=theme.BG)
        self.en_button.pack(side='left', padx=8)

        # -- start ----------------------------------------------------------
        self.start_button = theme.RoundedButton(
            self, 'START', command=self.start_listening, width=420, height=76,
            fill=theme.ACCENT, hover=theme.ACCENT_DARK, font_name='heading',
            bg=theme.BG, radius=22)
        self.start_button.pack(pady=22)

        self.prompt = tk.Label(self, text='', bg=theme.BG, fg=theme.TEXT_DIM,
                               font=theme.font('body'))
        self.prompt.pack()

        # -- transcript -----------------------------------------------------
        panels = tk.Frame(self, bg=theme.BG)
        panels.pack(fill='both', expand=True, padx=40, pady=(20, 30))

        self.you_title, self.you_label = self._panel(panels, 'You said',
                                                     theme.TEXT_DIM)
        self.pixi_title, self.pixi_label = self._panel(panels, 'Pixi says',
                                                       theme.ACCENT)

    def _panel(self, parent, title, color):
        card = tk.Frame(parent, bg=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.BORDER)
        card.pack(fill='both', expand=True, pady=7)

        title_label = tk.Label(card, text=title.upper(), bg=theme.SURFACE,
                               fg=color, font=theme.font('small'), anchor='w')
        title_label.pack(fill='x', padx=18, pady=(12, 2))

        body = tk.Label(card, text='---', bg=theme.SURFACE, fg=theme.TEXT,
                        font=theme.font('subheading'), anchor='w',
                        justify='left', wraplength=900)
        body.pack(fill='both', expand=True, padx=18, pady=(0, 14))
        return title_label, body

    # -- language -----------------------------------------------------------
    def set_language(self, language):
        if self.busy:
            return
        self.language = language
        self._apply_language()

    def _apply_language(self):
        active, inactive = self.bn_button, self.en_button
        if self.language == config.LANG_ENGLISH:
            active, inactive = self.en_button, self.bn_button
        active.set_fill(theme.ACCENT, theme.ACCENT_DARK)
        inactive.set_fill(theme.SURFACE, theme.SURFACE_HI)

        strings = STRINGS[self.language]
        self.start_button.set_text(strings['start'])
        self.prompt.config(text=strings['idle'], font=theme.speech_font(self.language))
        self.you_title.config(text=strings['you_said'].upper())
        self.pixi_title.config(text=strings['pixi_said'].upper())

        # Bengali needs its own font or the labels render as empty boxes
        answer_font = theme.speech_font(self.language)
        self.you_label.config(font=answer_font)
        self.pixi_label.config(font=answer_font)

    # -- the conversation ---------------------------------------------------
    def start_listening(self):
        """START was pressed.  Listen and answer on a worker thread."""
        if self.busy:
            return
        self.busy = True
        self.start_button.set_enabled(False)
        strings = STRINGS[self.language]
        self.prompt.config(text=strings['listening'])
        self.status_pill.set('Listening', theme.AMBER)
        self.you_label.config(text='...')
        self.pixi_label.config(text='...')

        thread = threading.Thread(target=self._conversation_worker)
        thread.daemon = True
        thread.start()

    def _conversation_worker(self):
        language = self.language
        text, error = speech.listen(language)

        if error:
            self.after(0, self._finish, None, error, language)
            return

        self.after(0, self._show_question, text, language)

        answer = generate_response(text, self.responses.get(language, {}),
                                   language)
        self.after(0, self._show_answer, answer, language)

        speech.speak(answer, language)
        self.after(0, self._finish, text, None, language)

    def _show_question(self, text, language):
        self.you_label.config(text=text)
        self.status_pill.set('Searching the catalogue', theme.ACCENT)
        self.prompt.config(text=STRINGS[language]['thinking'])

    def _show_answer(self, answer, language):
        self.pixi_label.config(text=answer)
        self.status_pill.set('Speaking', theme.GREEN)
        self.prompt.config(text=STRINGS[language]['speaking'])

    def _finish(self, text, error, language):
        if error:
            self.pixi_label.config(text=error)
            self.status_pill.set(error[:34], theme.RED)
        else:
            self.status_pill.set('Ready', theme.TEXT_DIM)
        self.prompt.config(text=STRINGS[language]['idle'])
        self.start_button.set_enabled(True)
        self.busy = False

    # -- housekeeping -------------------------------------------------------
    def on_leave(self):
        """Called by the shell when we switch away from this mode."""
        pass

    def _go_back(self):
        if self.busy:
            return
        if self.on_back:
            self.on_back()


# Running this file on its own still works, the way it always did
if __name__ == '__main__':
    root = tk.Tk()
    root.title('Librarian Robot Version 1.0')
    root.geometry('1200x800')
    root.configure(bg=theme.BG)
    theme.init_fonts(root)
    LibrarianMode(root).pack(fill='both', expand=True)
    root.mainloop()
