# Speech input and output for Pixi.
#
# Bengali and English are handled by different engines:
#   - Bengali goes out through gTTS (needs the internet, but pyttsx3 has no
#     Bengali voice on either Windows or the Pi)
#   - English goes out through pyttsx3 so it still works offline
#
# Both of them block, so every caller runs them on a worker thread.

import os
import subprocess
import tempfile
import threading

import speech_recognition as sr

import config

# gTTS and playsound are only needed for Bengali, and pyttsx3 only for
# English.  Import them lazily so a machine missing one engine can still run
# the other mode.
_engine = None
_engine_lock = threading.Lock()

# Only one thing may talk at a time or the two engines fight over the sound card
_speak_lock = threading.Lock()

recognizer = sr.Recognizer()


def _get_engine():
    """Create the pyttsx3 engine once and reuse it."""
    global _engine
    with _engine_lock:
        if _engine is None:
            import pyttsx3
            _engine = pyttsx3.init()
            rate = _engine.getProperty('rate')
            _engine.setProperty('rate', rate - 30)
            # Prefer a female voice if the platform has one.  On the Pi
            # (espeak) there is usually only one voice, so guard the index.
            voices = _engine.getProperty('voices')
            if len(voices) > 1:
                _engine.setProperty('voice', voices[1].id)
        return _engine


# ---------------------------------------------------------------------------
# Listening
# ---------------------------------------------------------------------------
def listen(language=config.LANG_ENGLISH):
    """Record one phrase from the microphone and return the text.

    Returns (text, error).  Exactly one of them is None.
    """
    stt_code = config.STT_CODES.get(language, 'en-US')
    try:
        with sr.Microphone() as source:
            print("Listening... (%s)" % stt_code)
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source,
                                      timeout=config.LISTEN_TIMEOUT,
                                      phrase_time_limit=config.PHRASE_TIME_LIMIT)
    except sr.WaitTimeoutError:
        # Nobody started talking before the timeout ran out
        return None, "I did not hear anything. Please try again."
    except OSError as e:
        # No microphone plugged in, or ALSA is busy
        return None, "Microphone not available: %s" % e

    try:
        print("Recognizing...")
        text = recognizer.recognize_google(audio, language=stt_code)
        print("You have said: %s" % text)
        return text, None
    except sr.UnknownValueError:
        return None, "Sorry, I could not understand that."
    except sr.RequestError as e:
        return None, "Speech service unreachable: %s" % e


# ---------------------------------------------------------------------------
# Speaking
# ---------------------------------------------------------------------------
def speak(text, language=config.LANG_ENGLISH):
    """Say the text out loud.  Blocks until it has finished speaking."""
    if not text:
        return

    with _speak_lock:
        if language == config.LANG_BENGALI:
            _speak_bengali(text)
        else:
            _speak_english(text)


# Command line players to fall back on when playsound is not installed.
# playsound is fragile - it needs gstreamer on Linux and its installer is
# broken on newer setuptools - so we do not depend on it being there.
MP3_PLAYERS = [
    ['afplay'],                    # macOS, always present
    ['mpg123', '-q'],              # Raspbian, apt install mpg123
    ['mpg321', '-q'],
    ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet'],
    ['cvlc', '--play-and-exit', '--intf', 'dummy'],
]


def _play_mp3(path):
    """Play an mp3 file. Returns True if some player actually managed it."""
    try:
        from playsound import playsound
        playsound(path)
        return True
    except ImportError:
        pass
    except Exception as e:
        print("playsound failed, trying a command line player: %s" % e)

    for player in MP3_PLAYERS:
        try:
            subprocess.call(player + [path])
            return True
        except OSError:
            # That player is not installed, try the next one
            continue

    print("No mp3 player found. Install mpg123 (Raspbian) to hear Bengali.")
    return False


def _speak_bengali(text):
    from gtts import gTTS

    # A player cannot delete the file while it is playing on Windows, so we
    # write it out, play it, then clean up ourselves.
    handle, path = tempfile.mkstemp(suffix='.mp3')
    os.close(handle)
    try:
        tts = gTTS(text=text, lang=config.LANG_BENGALI)
        tts.save(path)
        _play_mp3(path)
    except Exception as e:
        print("Bengali speech failed: %s" % e)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _speak_english(text):
    try:
        engine = _get_engine()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("English speech failed: %s" % e)


def speak_async(text, language=config.LANG_ENGLISH, done=None):
    """Speak on a worker thread so the Tk main loop keeps running."""

    def worker():
        speak(text, language)
        if done:
            done()

    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    return thread
