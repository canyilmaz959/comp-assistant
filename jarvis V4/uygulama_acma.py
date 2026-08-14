import os
def open_application(komut):
    apps = {
        "not defteri": "notepad.exe",
        "notepad": "notepad.exe",
        "paint": "mspaint.exe",
        "hesap makinesi": "calc.exe",
        "calculator": "calc.exe",
        "tarayıcı": "C:\\Users\\can\\AppData\\Local\\Programs\\Opera GX\\opera.exe",
        "spotify": "Spotify.exe",
        "netflix": "Netflix.exe",
        "microsoft store": "WinStore.App.exe",
        "mağaza": "WinStore.App.exe",
        "store": "WinStore.App.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "dosya gezgini": "explorer.exe",
        "steam": "C:\\Program Files (x86)\\Steam\\steam.exe",
        "mail": "outlook.exe",
        "outlook": "outlook.exe",
    }
    for key in apps:
        if key in komut:
            try:
                os.startfile(apps[key])
                return f"{key} açılıyor."
            except Exception as e:
                return f"{key} açılamadı: {str(e)}"
    return "Uygulamayı bilmiyorum."