from jarvis import TurkishVoiceAssistant
from uygulama_acma import open_application
from web_arama import search_web
from hava_durumu import get_weather
from zaman import get_time
import time

def process_command(command):
    if "merhaba" in command:
        return "Merhaba! Size nasıl yardımcı olabilirim?"
    elif "hava durumu" in command:
        return get_weather()
    elif "saat" in command or "tarih" in command:
        return get_time()
    elif "aç" in command:
        return open_application(command)
    elif "ara" in command:
        query = command.replace("ara", "").strip()
        return search_web(query)
    elif "kapat" in command:
        return "KAPAT"
    else:
        return "Bu komutu bilmiyorum."

def main():
    assistant = TurkishVoiceAssistant()
    assistant.speak("Jarvis hazır.")
    
    while True:
        cmd = assistant.listen()
        response = process_command(cmd)
        if response == "KAPAT":
            assistant.speak("Görüşürüz!")
            break
        assistant.speak(response)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
