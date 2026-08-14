import speech_recognition as sr
import pyttsx3
import os
import requests
import datetime
import webbrowser
import threading
import time
from pathlib import Path

class TurkishVoiceAssistant:
    def __init__(self):
        # Ses motoru kurulumu
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 170)
        
        # Ses seçimi (Türkçe ses varsa kullan)
        voices = self.engine.getProperty("voices")
        for voice in voices:
            if "turkish" in voice.name.lower() or "tr" in voice.id.lower():
                self.engine.setProperty("voice", voice.id)
                break
        else:
            self.engine.setProperty("voice", voices[0].id)
        
        # Ses tanıma
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Kalibrasyon
        self.calibrate_microphone()
        
    def calibrate_microphone(self):
        """Mikrofon kalibrasyon"""
        with self.microphone as source:
            print("🔧 Mikrofon kalibre ediliyor...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print("✅ Kalibrasyon tamamlandı")
    
    def speak(self, text):
        """Metni sesle söyle"""
        print(f"🤖 Jarvis: {text}")
        # Threading ile konuşmayı ayrı thread'de çalıştır
       

    
    def _speak_worker(self, text):
        """Konuşma worker thread'i"""
        self.engine.say(text)
        self.engine.runAndWait()
    
    def listen(self, timeout=5):
        """Ses dinle ve metne çevir"""
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
            print("❌ Söylenen anlaşılmadı")
            return "anlamadım"
        except sr.RequestError as e:
            print(f"❌ Google API hatası: {e}")
            return "api_hatası"
    
    def get_weather(self, city=""):
        """Hava durumu bilgisi al"""
        try:
            if city:
                url = f"https://wttr.in/{city}?format=3&lang=tr"
            else:
                url = "https://wttr.in/?format=3&lang=tr"
            
            response = requests.get(url, timeout=5)
            weather = response.text.strip()
            return f"Hava durumu: {weather}"
        except requests.RequestException:
            return "Hava durumu bilgisi alınamadı"
    
    def get_time(self):
        """Şu anki zamanı söyle"""
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d %B %Y")
        
        # Türkçe ay isimleri
        months_tr = {
            "January": "Ocak", "February": "Şubat", "March": "Mart",
            "April": "Nisan", "May": "Mayıs", "June": "Haziran",
            "July": "Temmuz", "August": "Ağustos", "September": "Eylül",
            "October": "Ekim", "November": "Kasım", "December": "Aralık"
        }
        
        for eng, tr in months_tr.items():
            date_str = date_str.replace(eng, tr)
        
        return f"Saat {time_str}, tarih {date_str}"
    
    def open_application(self, app_name):
        """Uygulama aç"""
        apps = {
            "not defteri": "notepad.exe",
            "notepad": "notepad.exe",
            "hesap makinesi": "calc.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "boyama": "mspaint.exe",
            "tarayıcı": "chrome.exe",
            "browser": "chrome.exe",
            "dosya gezgini": "explorer.exe",
            "explorer": "explorer.exe"
        }
        
        for key in apps:
            if key in app_name:
                try:
                    os.system(apps[key])
                    return f"{key} açıldı"
                except Exception:
                    return f"{key} açılamadı"
        
        return "Bu uygulamayı bilmiyorum"
    
    def search_web(self, query):
        """Web'de arama yap"""
        try:
            search_url = f"https://www.google.com/search?q={query}"
            webbrowser.open(search_url)
            return f"{query} için arama yapıldı"
        except Exception:
            return "Arama yapılamadı"
    
    def process_command(self, command):
        """Komutları işle"""
        if not command or command in ["anlamadım", "api_hatası", "timeout"]:
            if command == "timeout":
                return "Bir şey söylemediniz"
            elif command == "api_hatası":
                return "İnternet bağlantı sorunu"
            else:
                return "Anlamadım, tekrar söyler misiniz?"
        
        # Selamlama
        if any(word in command for word in ["merhaba", "selam", "hello"]):
            return "Merhaba! Size nasıl yardımcı olabilirim?"
        
        # Hava durumu
        elif "hava durumu" in command or "hava" in command:
            city = ""
            if "ankara" in command:
                city = "ankara"
            elif "istanbul" in command:
                city = "istanbul"
            elif "izmir" in command:
                city = "izmir"
            return self.get_weather(city)
        
        # Saat ve tarih
        elif any(word in command for word in ["saat", "zaman", "tarih"]):
            return self.get_time()
        
        # Uygulama açma
        elif "aç" in command:
            return self.open_application(command)
        
        # Web araması
        elif any(word in command for word in ["ara", "arama", "search"]):
            query = command.replace("ara", "").replace("arama", "").replace("search", "").strip()
            if query:
                return self.search_web(query)
            else:
                return "Ne aramak istiyorsunuz?"
        
        # Müzik çalma
        elif any(word in command for word in ["müzik", "şarkı", "music"]):
            try:
                webbrowser.open("https://open.spotify.com")
                return "Spotify açıldı"
            except:
                return "Müzik uygulaması açılamadı"
        
        # Kapatma
        elif any(word in command for word in ["kapat", "çık", "bye", "exit", "quit"]):
            return "KAPAT"
        
        # Yardım
        elif "yardım" in command or "help" in command:
            help_text = """
            Yapabileceklerim:
            • Hava durumu sorabilirsiniz
            • Saat ve tarihi söyleyebilirim
            • Uygulamaları açabilirim (not defteri, hesap makinesi, paint)
            • Web'de arama yapabilirim
            • Müzik uygulaması açabilirim
            """
            return help_text.strip()
        
        # Bilinmeyen komut
        else:
            return "Bu komutu henüz öğrenmedim. 'Yardım' diyerek neler yapabileceğimi öğrenebilirsiniz."
    
    def run(self):
        """Ana döngü"""
        self.speak("Jarvis hazır. Size nasıl yardımcı olabilirim?")
        
        consecutive_errors = 0
        max_errors = 3
        
        while True:
            try:
                command = self.listen()
                response = self.process_command(command)
                
                if response == "KAPAT":
                    self.speak("Görüşürüz! İyi günler.")
                    break
                
                self.speak(response)
                consecutive_errors = 0  # Başarılı işlem sonrası hata sayacını sıfırla
                
            except KeyboardInterrupt:
                self.speak("Program sonlandırılıyor. Görüşürüz!")
                break
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Hata: {e}")
                
                if consecutive_errors >= max_errors:
                    self.speak("Çok fazla hata oluştu. Program sonlandırılıyor.")
                    break
                else:
                    self.speak("Bir hata oluştu, tekrar deneyin.")
            
            # Kısa bekleme
            time.sleep(0.5)

def main():
    """Ana fonksiyon"""
    try:
        assistant = TurkishVoiceAssistant()
        assistant.run()
    except Exception as e:
        print(f"Program başlatılamadı: {e}")
        print("Gerekli kütüphanelerin yüklü olduğundan emin olun:")
        print("pip install speechrecognition pyttsx3 requests")

if __name__ == "__main__":
    main()