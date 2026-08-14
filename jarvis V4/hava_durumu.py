import requests

def get_weather(city=""):
    try:
        if city:
            url = f"https://wttr.in/{city}?format=3&lang=tr"
        else:
            url = "https://wttr.in/?format=3&lang=tr"
        response = requests.get(url, timeout=5)
        return f"Hava durumu: {response.text.strip()}"
    except requests.RequestException:
        return "Hava durumu bilgisi alınamadı"
