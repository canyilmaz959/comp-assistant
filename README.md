# 🎙️ My PC Assistant

Python ile geliştirilmiş, sesli komutları algılayarak bilgisayar üzerinde çeşitli görevleri yerine getiren modüler bir masaüstü asistanı projesi.

---

## ✨ Özellikler

* 🗣️ **Türkçe Sesli İletişim:** `SpeechRecognition` ile ses tanıma ve `pyttsx3` / `gTTS` ile sesli geri bildirim.
* ⛅ **Hava Durumu:** Anlık hava durumu bilgilerini hızlıca öğrenme].
* 🕒 **Saat & Tarih:** Güncel saat ve tarih sorgulama[cite: 4, 7].
* 🚀 **Uygulama Başlatıcı:** Not Defteri, Hesap Makinesi, Tarayıcı gibi sık kullanılan programları sesle açma.
* 🌐 **Web Araması:** Tarayıcı üzerinden doğrudan Google araması gerçekleştirme.

---

## 🛠️ Kullanılan Teknolojiler

* **Python**
* `SpeechRecognition` (Google Speech API)
* `pyttsx3` & `gTTS` (Metinden Sese Çeviri)
* `pygame` (Ses Yönetimi)
* `requests` (Hava Durumu API İstekleri)

---

## 🚀 Gelecek Planları (Roadmap)

- [ ] LLM (OpenAI / Gemini / Groq) entegrasyonu ile akıllı niyet analizi (Intent Parsing)
- [ ] Minimalist masaüstü arayüzü (CustomTkinter / PyQt)
- [ ] Tek tıkla kurulum için `.exe` paketi haline getirme
