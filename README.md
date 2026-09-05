# LyBot — Telegram Music Search Bot

بوت بحث موسيقى مستقل لتليجرام يعمل داخل الخاص والكروبات بدون تشغيل داخل المكالمات الصوتية.

## المزايا

- البحث عبر YouTube وSoundCloud وBandcamp من خلال `yt-dlp`.
- ترتيب النتائج حسب تطابق اسم الأغنية والفنان والمصدر.
- دعم روابط YouTube وSoundCloud، ومحاولة استخراج بيانات روابط Spotify وApple Music.
- أزرار لاختيار أفضل نتيجة وإظهار الرابط المناسب.
- لا يحتاج حساب Telegram مساعداً أو Session String.

## الأوامر

```text
/play Skyfall Adele
/p Skyfall Adele
/vplay Skyfall Adele
/song Skyfall Adele
/search Skyfall Adele
/help
```

أوامر `/pause` و`/resume` و`/skip` و`/stop` و`/queue` تعرض تنبيهاً بأن ميزة المكالمات أزيلت.

## التشغيل

المتطلبات:

- Python 3.11 أو أحدث
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`

```bash
pip install -r requirements.txt
python bot.py
```

على Pella استخدم أمر التشغيل:

```bash
python bot.py
```

وأضف المتغيرات الثلاثة الموجودة في `.env.example` كـ Secrets.

## Docker

```bash
docker compose up -d --build
```

## ملاحظات

هذه النسخة تعرض روابط من المصادر العامة ولا تتجاوز الاشتراكات أو الحماية ولا تخزن الأغاني بشكل دائم.