# 🎙️ My PC Assistant

Python ile geliştirilmiş, sesli komutları algılayarak bilgisayar üzerinde çeşitli görevleri yerine getiren modüler bir masaüstü asistanı projesi.

---

## ✨ Özellikler

* 🗣️ **Türkçe Sesli İletişim:** `SpeechRecognition` ile ses tanıma ve `pyttsx3` / `gTTS` ile sesli geri bildirim[cite: 2].
* ⛅ **Hava Durumu:** Anlık hava durumu bilgilerini hızlıca öğrenme[cite: 1, 4].
* 🕒 **Saat & Tarih:** Güncel saat ve tarih sorgulama[cite: 4, 7].
* 🚀 **Uygulama Başlatıcı:** Not Defteri, Hesap Makinesi, Tarayıcı gibi sık kullanılan programları sesle açma[cite: 4, 5].
* 🌐 **Web Araması:** Tarayıcı üzerinden doğrudan Google araması gerçekleştirme[cite: 4, 6].

---

## 🛠️ Kullanılan Teknolojiler

* **Python**[cite: 1, 2, 4, 5, 6, 7]
* `SpeechRecognition` (Google Speech API)[cite: 2]
* `pyttsx3` & `gTTS` (Metinden Sese Çeviri)[cite: 2]
* `pygame` (Ses Yönetimi)[cite: 2]
* `requests` (Hava Durumu API İstekleri)[cite: 1]

---

## 🚀 Gelecek Planları (Roadmap)

- [ ] LLM (OpenAI / Gemini / Groq) entegrasyonu ile akıllı niyet analizi (Intent Parsing)
- [ ] Minimalist masaüstü arayüzü (CustomTkinter / PyQt)
- [ ] Tek tıkla kurulum için `.exe` paketi haline getirme
