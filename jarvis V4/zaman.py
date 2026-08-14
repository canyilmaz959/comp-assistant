import datetime

def get_time():
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d %B %Y")

    months_tr = {
        "January": "Ocak", "February": "Şubat", "March": "Mart",
        "April": "Nisan", "May": "Mayıs", "June": "Haziran",
        "July": "Temmuz", "August": "Ağustos", "September": "Eylül",
        "October": "Ekim", "November": "Kasım", "December": "Aralık"
    }

    for eng, tr in months_tr.items():
        date_str = date_str.replace(eng, tr)

    return f"Saat {time_str}, tarih {date_str}"
