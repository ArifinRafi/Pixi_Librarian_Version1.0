import speech_recognition as sr
import pyttsx3
import datetime
import wikipedia
import pyjokes
import random
import json
import os

# Initialize the recognizer and the speech engine
listener = sr.Recognizer()
pixi = pyttsx3.init()
rate = pixi.getProperty('rate')
pixi.setProperty('rate', rate - 30)
voices = pixi.getProperty('voices')
pixi.setProperty('voice', voices[1].id)

def talk(text):
    pixi.say(text)
    pixi.runAndWait()

def wish_me():
    hour = int(datetime.datetime.now().hour)
    if hour < 12:
        talk("Good Morning Sir!")
    elif hour < 18:
        talk("Good Afternoon Sir!")
    else:
        talk("Good Evening Sir!")

def load_responses(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"The file {file_path} does not exist.")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from the file {file_path}.")
        return None

# Load responses from 'responses.json' file
file_path = 'general_responses.json'
responses_data = load_responses(file_path)
if responses_data is None:
    print("Failed to load responses. Exiting...")
    exit(1)
else:
    print("Loaded responses:", responses_data)

keywords_responses = responses_data['keywords_responses']

def get_response(command):
    for keyword, responses in keywords_responses.items():
        if keyword in command:
            return random.choice(responses)

    if 'time' in command:
        return datetime.datetime.now().strftime('%I:%M %p')

    if 'jokes' in command or 'joke' in command:
        return pyjokes.get_joke()

    # Wikipedia information
    if 'tell me about' in command or 'what is' in command or 'who is' in command:
        query = command.replace('tell me about', '').replace('what is', '').replace('who is', '').strip()
        try:
            return wikipedia.summary(query, sentences=1)
        except wikipedia.exceptions.DisambiguationError as e:
            return "There are multiple results. Please be more specific."
        except wikipedia.exceptions.PageError:
            return "Sorry, I couldn't find any information on that."

    return "Sorry, I do not understand. Please say it again."

def listen():
    with sr.Microphone() as source:
        print("Listening...")
        listener.adjust_for_ambient_noise(source)
        audio = listener.listen(source, timeout=5, phrase_time_limit=10)
        try:
            print("Recognizing...")
            command = listener.recognize_google(audio)
            print(f"You said: {command}")
            return command.lower()
        except sr.UnknownValueError:
            return "Sorry, I did not understand that."
        except sr.RequestError as e:
            return f"Request error: {e}"

def main():
    talk(random.choice(["Hello Boss. I am Pixi, your autonomous humanoid robot. How can I help you?", "Hi Sir! I am Gorky. Ask me your question please.", "Hello Sir, I am Gorky. How may I help?", "It's Gorky. How can I help?"]))
    wish_me()
    while True:
        command = listen()
        if command:
            response = get_response(command)
            if response:
                print(f"Gorky: {response}")
                talk(response)

if __name__ == "__main__":
    main()
