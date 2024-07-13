import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import os
import json
import tkinter as tk

# Initialize the recognizer
recognizer = sr.Recognizer()

# Function to load responses from JSON file
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
file_path = 'responses.json'
responses = load_responses(file_path)
if responses is None:
    print("Failed to load responses. Exiting...")
    exit(1)
else:
    print("Loaded responses:", responses)

def listen():
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)  # Adjust for ambient noise
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("Recognizing...")
            text = recognizer.recognize_google(audio, language="bn-BD")
            print(f"You have said: {text}")
            return text
        except sr.WaitTimeoutError:
            print("Listening timed out while waiting for phrase to start")
            return None
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None

def generate_response(input_text):
    print(f"Generating response for: {input_text}")
    for question, response in responses.items():
        if question in input_text:
            print(f"Found matching response: {response}")
            return response
    return "দুঃখিত, আমি আপনার প্রশ্নের উত্তর জানি না।"

def respond(text, response_label):
    if not text:
        return
    response = generate_response(text)
    print(f"Responding with: {response}")
    response_label.config(text=response)  # Update the label with the response text
    tts = gTTS(text=response, lang='bn')
    tts.save("response.mp3")
    playsound("response.mp3")
    os.remove("response.mp3")

def close_program():
    print("Closing the program.")
    root.destroy()
    os._exit(0)  # Ensure the program terminates

def pixi():
    global root, input_label, response_label
    root = tk.Tk()
    root.title("Librarian Robot Version 1.0")
    window_width = 1200
    window_height = 800
    root.geometry(f"{window_width}x{window_height}")

    input_label = tk.Label(root, text="You said:", wraplength=window_width - 20, justify="left")
    input_label.pack(pady=10)
    
    response_label = tk.Label(root, text="Response:", wraplength=window_width - 20, justify="left")
    response_label.pack(pady=10)

    close_button = tk.Button(root, text="Close", command=close_program)
    close_button.pack(pady=20)

    def listen_and_respond():
        question = listen()
        if question:
            input_label.config(text=f"You said: {question}")
            respond(question, response_label)
        else:
            print("Sorry, I could not understand. Please try again.")
    
    listen_button = tk.Button(root, text="Listen", command=listen_and_respond)
    listen_button.pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    pixi()
