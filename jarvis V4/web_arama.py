import webbrowser

def search_web(query):
    try:
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open(url)
        return f"{query} için arama yapıldı"
    except Exception:
        return "Arama yapılamadı"
