import speech_recognition as sr
import os
import requests
import datetime
import webbrowser
import time
from pathlib import Path
import tempfile
from gtts import gTTS
import pygame

class JarvisAssistant:
    def __init__(self):
        """Jarvis asistan başlatma"""
        print("Jarvis başlatılıyor...")
        
        # Ses dosyaları için temp klasör
        self.temp_dir = Path(tempfile.gettempdir()) / "jarvis_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Pygame ses sistemi
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
        
        # Ses tanıma sistemi
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Mikrofon kalibrasyonu
        self.setup_microphone()
        
        print("✅ Jarvis hazır!")
    
    def setup_microphone(self):
        """Mikrofon kurulumu ve kalibrasyon"""
        print("🎤 Mikrofon kalibre ediliyor...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        print("✅ Mikrofon hazır!")
    
    def speak(self, text):
        """Google TTS ile konuşma"""
        print(f"🤖 Jarvis: {text}")
        
        try:
            # Google TTS ile ses oluştur
            tts = gTTS(text=text, lang='tr', slow=False)
            
            # Geçici ses dosyası
            audio_file = self.temp_dir / f"speech_{int(time.time())}.mp3"
            tts.save(str(audio_file))
            
            # Ses çal
            pygame.mixer.music.load(str(audio_file))
            pygame.mixer.music.play()
            
            # Çalma bitene kadar bekle
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Temp dosyayı temizle
            try:
                audio_file.unlink()
            except:
                pass
                
        except Exception as e:
            print(f"❌ TTS Hatası: {e}")
            print("🌐 İnternet bağlantınızı kontrol edin!")
    
    def listen(self, timeout=5):
        """Ses dinleme ve tanıma"""
        with self.microphone as source:
            print("🎤 Dinleniyor...")
            try:
                # Ses kaydet
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)
                
                # Google STT ile tanıma
                command = self.recognizer.recognize_google(audio, language="tr-TR")
                print(f"👤 Sen: {command}")
                return command.lower()
                
            except sr.WaitTimeoutError:
                print("⏰ Zaman aşımı")
                return "timeout"
            except sr.UnknownValueError:
                print("❌ Anlaşılmadı")
                return "anlaşılmadı"
            except sr.RequestError as e:
                print(f"❌ Google API hatası: {e}")
                return "api_hatası"
    
    def ask_and_wait(self, question, timeout=8):
        """Soru sor ve cevabı bekle"""
        self.speak(question)
        return self.listen(timeout=timeout)
    
    def get_weather(self, city=""):
        """Hava durumu bilgisi"""
        try:
            if city:
                # Şehir isimlerini temizle
                city = city.replace("'nin", "").replace("'nın", "").strip()
                url = f"https://wttr.in/{city}?format=3&lang=tr"
            else:
                url = "https://wttr.in/?format=3&lang=tr"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                weather = response.text.strip()
                return weather
            else:
                return "Hava durumu alınamadı"
                
        except requests.RequestException:
            return "Hava durumu servisi erişilemiyor"
    
    def get_time_date(self):
        """Saat ve tarih bilgisi"""
        now = datetime.datetime.now()
        
        # Türkçe ay isimleri
        months = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
            5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
            9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        
        # Türkçe gün isimleri
        days = {
            0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe",
            4: "Cuma", 5: "Cumartesi", 6: "Pazar"
        }
        
        time_str = now.strftime("%H:%M")
        day_name = days[now.weekday()]
        date_str = f"{now.day} {months[now.month]} {now.year}"
        
        return f"Saat {time_str}. Bugün {day_name}, {date_str}"
    
    def open_application(self, app_name):
        """Uygulama açma"""
        apps = {
            "not defteri": "notepad.exe",
            "notepad": "notepad.exe",
            "hesap makinesi": "calc.exe",
            "hesap makinası": "calc.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "boyama": "mspaint.exe",
            "opera": "C:\\Users\\can\\AppData\\Local\\Programs\\Opera GX\\opera.exe",
            "tarayıcı": "C:\\Users\\can\\AppData\\Local\\Programs\\Opera GX\\opera.exe",
            "dosya gezgini": "explorer.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "komut satırı": "cmd.exe",
            "spotify": "spotify.exe",
            "müzik": "spotify.exe",
        }
        
        for app_key, app_exe in apps.items():
            if app_key in app_name.lower():
                try:
                    os.system(f"start {app_exe}")
                    return f"{app_key} açıldı"
                except Exception as e:
                    return f"{app_key} açılamadı: {str(e)}"
        
        return "Bu uygulamayı bilmiyorum"
    
    def web_search(self, query):
        """Web araması"""
        if not query or query.strip() == "":
            return "Arama terimi bulunamadı"
        
        try:
            search_url = f"https://www.google.com/search?q={query.strip()}"
            webbrowser.open(search_url)
            return f"'{query}' için arama yapıldı"
        except Exception as e:
            return f"Arama yapılamadı: {str(e)}"
    
    def process_command(self, command):
        """Komut işleme merkezi"""
        
        # Boş veya hatalı komutlar
        if not command or command in ["anlaşılmadı", "api_hatası", "timeout"]:
            if command == "timeout":
                return "Bir şey söylemediniz"
            elif command == "api_hatası":
                return "İnternet bağlantısında sorun var"
            else:
                return "Anlamadım, tekrar söyler misiniz?"
        
        # Selamlama komutları
        if any(word in command for word in ["merhaba", "selam", "hello", "hi", "hey"]):
            greetings = [
                "Merhaba! Size nasıl yardımcı olabilirim?",
                "Selam! Bugün ne yapalım?",
                "Merhaba! Hizmetinizdeyim.",
                "Selam! Ne istiyorsunuz?"
            ]
            import random
            return random.choice(greetings)
        
        # Hava durumu
        elif any(word in command for word in ["hava", "hava durumu", "weather"]):
            city = ""
            cities = ["ankara", "istanbul", "izmir", "bursa", "antalya", "adana", "konya"]
            for city_name in cities:
                if city_name in command:
                    city = city_name
                    break
            
            weather_info = self.get_weather(city)
            if city:
                return f"{city.title()} {weather_info}"
            else:
                return weather_info
        
        # Saat ve tarih
        elif any(word in command for word in ["saat", "zaman", "tarih", "gün"]):
            return self.get_time_date()
        
        # Uygulama açma
        elif any(word in command for word in ["aç", "açar", "başlat", "çalıştır"]):
            return self.open_application(command)
        
        # Web araması
        elif any(word in command for word in ["ara", "arama", "search", "google"]):
            # Komut içinde arama terimi var mı?
            query = command
            for word in ["ara", "arama", "search", "google", "da", "de", "için"]:
                query = query.replace(word, "")
            query = query.strip()
            
            if not query:
                # İnteraktif arama
                search_term = self.ask_and_wait("Ne aramak istiyorsunuz?", timeout=10)
                if search_term and search_term not in ["anlaşılmadı", "api_hatası", "timeout"]:
                    return self.web_search(search_term)
                else:
                    return "Arama iptal edildi"
            else:
                return self.web_search(query)
        
        # YouTube
        elif any(word in command for word in ["youtube", "video", "müzik", "şarkı"]):
            search_term = command.replace("youtube", "").replace("video", "").replace("müzik", "").replace("şarkı", "").strip()
            if search_term:
                try:
                    youtube_url = f"https://www.youtube.com/results?search_query={search_term}"
                    webbrowser.open(youtube_url)
                    return f"YouTube'da '{search_term}' aranıyor"
                except:
                    return "YouTube açılamadı"
            else:
                try:
                    webbrowser.open("https://www.youtube.com")
                    return "YouTube açıldı"
                except:
                    return "YouTube açılamadı"
        
        # Kapatma komutları
        elif any(word in command for word in ["kapat", "çık", "exit", "bye", "görüşürüz", "hoşçakal"]):
            return "KAPAT"
        
        # Yardım
        elif any(word in command for word in ["yardım", "help", "ne yapabilirsin", "komutlar"]):
            help_text = """İşte yapabileceklerim:
            
🌤️  Hava durumu - 'Hava nasıl?' veya 'İstanbul hava durumu'
⏰  Saat tarih - 'Saat kaç?' veya 'Bugün hangi gün?'
🚀  Uygulama aç - 'Not defteri aç' veya 'Hesap makinesi çalıştır'
🔍  Web arama - 'Python ara' veya sadece 'ara'
🎵  YouTube - 'YouTube aç' veya 'müzik çal'
❌  Çıkış - 'Kapat' veya 'çık'
            
Başka sorularınız varsa çekinmeden sorun!"""
            return help_text
        
        # Nasılsın soruları
        elif any(word in command for word in ["nasılsın", "nasıl", "iyi misin"]):
            responses = [
                "İyiyim, teşekkür ederim! Sen nasılsın?",
                "Harikayım! Size yardım etmeye hazırım.",
                "Her zamanki gibi harika! Ne yapmak istiyorsun?",
                "Mükemmelim! Bugün ne işinize yarayabilirim?"
            ]
            import random
            return random.choice(responses)
        
        # Bilinmeyen komutlar
        else:
            unknown_responses = [
                "Bu komutu henüz öğrenmedim. 'Yardım' diyerek neler yapabileceğimi öğrenebilirsiniz.",
                "Anlamadım. Başka nasıl diyebilirim?",
                "Bu konuda bilgim yok. Farklı bir şey dener misiniz?",
                "Henüz bu komutu bilmiyorum. 'Yardım' diyerek öğrenebilirsiniz."
            ]
            import random
            return random.choice(unknown_responses)
    
    def run(self):
        """Ana program döngüsü"""
        # Başlangıç mesajı
        self.speak("Jarvis hazır! Size nasıl yardımcı olabilirim?")
        
        error_count = 0
        max_errors = 3
        
        while True:
            try:
                # Komut dinle
                command = self.listen(timeout=30)  # 30 saniye timeout
                
                # Komut işle
                response = self.process_command(command)
                
                # Kapatma kontrolü
                if response == "KAPAT":
                    self.speak("Görüşmek üzere! İyi günler dilerim.")
                    break
                
                # Cevap ver
                self.speak(response)
                
                # Hata sayacını sıfırla
                error_count = 0
                
                # Kısa bekleme
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\n⚠️  Program kullanıcı tarafından durduruldu")
                self.speak("Program sonlandırılıyor. Hoşçakalın!")
                break
                
            except Exception as e:
                error_count += 1
                print(f"❌ Beklenmeyen hata: {e}")
                
                if error_count >= max_errors:
                    print(f"⚠️  {max_errors} hata oluştu, program sonlandırılıyor")
                    self.speak("Çok fazla hata oluştu. Program kapanıyor.")
                    break
                else:
                    self.speak("Bir sorun oluştu, tekrar deneyin.")
        
        # Temizlik
        self.cleanup()
    
    def cleanup(self):
        """Program bitişinde temizlik"""
        try:
            # Pygame'i kapat
            pygame.mixer.quit()
            
            # Temp dosyaları temizle
            for file in self.temp_dir.glob("speech_*.mp3"):
                try:
                    file.unlink()
                except:
                    pass
                    
            print("🧹 Temizlik tamamlandı")
        except:
            pass

def main():
    """Ana fonksiyon"""
    print("=" * 50)
    print("JARVIS - Türkçe Sesli Asistan")
    print("=" * 50)
    
    try:
        # Gerekli kütüphaneleri kontrol et
        required_modules = ['gtts', 'pygame', 'speech_recognition', 'requests']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            print(f"❌ Eksik kütüphaneler: {', '.join(missing_modules)}")
            print("Kurulum için:")
            print(f"pip install {' '.join(missing_modules)}")
            return
        
        # Jarvis'i başlat
        jarvis = JarvisAssistant()
        jarvis.run()
        
    except Exception as e:
        print(f"❌ Program başlatılamadı: {e}")
        print("\n🔧 Sorun giderme:")
        print("1. Mikrofon bağlı ve çalışıyor mu?")
        print("2. İnternet bağlantınız var mı?")
        print("3. Gerekli kütüphaneler yüklü mü?")
        print("   pip install gtts pygame speechrecognition requests")

if __name__ == "__main__":
    main()