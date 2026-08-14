import speech_recognition as sr
import pyttsx3
import os
import requests

# Ses motoru
engine = pyttsx3.init()
engine.setProperty("rate", 170)  # Konuşma hızı
engine.setProperty("voice", engine.getProperty("voices")[0].id)

def speak(text):
    engine.say(text)
    engine.runAndWait()

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Dinleniyor...")
        r.adjust_for_ambient_noise(source)  # Ortam gürültüsünü azaltmak için
        audio = r.listen(source)
    try:
        command = r.recognize_google(audio, language="tr-TR")
        print("Sen:", command)
        return command.lower()
    except sr.UnknownValueError:
        print("Söylenen anlaşılmadı.")
        return "anlamadım"
    except sr.RequestError:
        print("Google API'ye erişilemiyor.")
        return "anlamadım"

def process_command(command):
    if "merhaba" in command:
        speak("Merhaba, nasılsın?")
    elif "hava durumu" in command:
        try:
            weather = requests.get("https://wttr.in/?format=3", timeout=5).text
            speak(f"Bugünkü hava: {weather}")
        except requests.RequestException:
            speak("Hava durumu alınamadı.")
    elif "not defteri aç" in command:
        try:
            os.system("notepad.exe")
            speak("Not defteri açıldı.")
        except Exception:
            speak("Not defteri açılamadı.")
    elif "kapat" in command:
        speak("Görüşürüz!")
        exit()
    else:
        speak("Bu komutu bilmiyorum. Ama öğrenebilirim!")

if __name__ == "__main__":
    speak("Jarvis hazır.")
    while True:
        cmd = listen()
        process_command(cmd)