import speech_recognition as sr
import pyttsx3
from gtts import gTTS
from pathlib import Path
import pygame
import tempfile

class TurkishVoiceAssistant:
    def __init__(self):
        print("Jarvis başlatılıyor...")
        
        self.temp_dir = Path(tempfile.gettempdir()) / "jarvis_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)

        
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 170)
        voices = self.engine.getProperty("voices")
        for voice in voices:
            if "turkish" in voice.name.lower() or "tr" in voice.id.lower():
                self.engine.setProperty("voice", voice.id)
                break
        else:
            self.engine.setProperty("voice", voices[0].id)

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.calibrate_microphone()

    def calibrate_microphone(self):
        with self.microphone as source:
            print("🔧 Mikrofon kalibre ediliyor...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print("✅ Kalibrasyon tamamlandı")

    def speak(self, text):
        print(f"🤖 Jarvis: {text}")
        try:
            tts = gTTS(text=text, lang="tr", slow=False)

    def _speak_worker(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self, timeout=5):
        with self.microphone as source:
            print("🎤 Dinleniyor...")
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                return "timeout"
        try:
            command = self.recognizer.recognize_google(audio, language="tr-TR")
            print(f"👤 Sen: {command}")
            return command.lower()
        except sr.UnknownValueError:
            return "anlamadım"
        except sr.RequestError:
            return "api_hatası"
