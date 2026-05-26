<p align="center">
  <img src="img/Veltrix.svg" alt="Veltrix" width="280" height="280" />
</p>

<p align="center">
  <strong>کنترل هوشمند شبکه — داشبورد حرفه‌ای مدیریت سرورهای x-ui/V2Ray</strong>
</p>

<p align="center">
  <a href="./CHANGELOG.md"><img src="https://img.shields.io/badge/نسخه-0.3.0-00bfa6?style=for-the-badge" alt="Version" /></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/لایسنس-تجاری-ef4444?style=for-the-badge" alt="License" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python" /></a>
</p>

<p align="center">
  <a href="https://github.com/iPmartNetwork/Veltrix/stargazers"><img src="https://img.shields.io/github/stars/iPmartNetwork/Veltrix?style=for-the-badge&color=f59e0b" alt="Stars" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix/network/members"><img src="https://img.shields.io/github/forks/iPmartNetwork/Veltrix?style=for-the-badge&color=8b5cf6" alt="Forks" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix/issues"><img src="https://img.shields.io/github/issues/iPmartNetwork/Veltrix?style=for-the-badge&color=ef4444" alt="Issues" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix"><img src="https://img.shields.io/github/repo-size/iPmartNetwork/Veltrix?style=for-the-badge&color=06b6d4" alt="Repo Size" /></a>
</p>

<p align="center">
  <a href="https://github.com/iPmartNetwork/Veltrix/commits/master"><img src="https://img.shields.io/github/last-commit/iPmartNetwork/Veltrix?style=for-the-badge&color=6366f1" alt="Last Commit" /></a>
  <a href="https://github.com/iPmartNetwork/Veltrix/graphs/contributors"><img src="https://img.shields.io/github/contributors/iPmartNetwork/Veltrix?style=for-the-badge&color=ec4899" alt="Contributors" /></a>
</p>

<p align="center">
  <a href="#-شروع-سریع">شروع سریع</a> •
  <a href="#-قابلیتها">قابلیت‌ها</a> •
  <a href="#-معماری">معماری</a> •
  <a href="#%EF%B8%8F-فناوری">فناوری</a> •
  <a href="#-استقرار">استقرار</a> •
  <a href="./README.md">🇬🇧 English</a> •
  <a href="./CHANGELOG.md">تغییرات</a>
</p>

---

## 📋 معرفی

**Veltrix** یک داشبورد عملیاتی self-hosted برای فروشندگان اوت‌باند، اپراتورهای شبکه و تیم‌هایی است که چندین سرور x-ui/V2Ray را مدیریت می‌کنند. مانیتورینگ سرور، بررسی سلامت اوت‌باندها، مدیریت رخدادها، اعلان‌ها، گزارش‌دهی و لایسنس تجاری در یک رابط حرفه‌ای واحد.

طراحی شده به عنوان **نرم‌افزار تجاری** با سرور لایسنس خصوصی.

---

## ⚡ شروع سریع

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/iPmartNetwork/Veltrix/master/scripts/install-linux.sh)
```

یا دستی:

```bash
git clone https://github.com/iPmartNetwork/Veltrix.git
cd Veltrix
sudo bash scripts/install-linux.sh
```

یا با Docker:

```bash
docker compose up -d
```

---

## ✨ قابلیت‌ها

### 🖥 مدیریت سرور

| قابلیت | توضیح |
|--------|-------|
| چند پنل | پشتیبانی x-ui، 3x-ui و Marzban |
| احراز هویت | نام‌کاربری/رمز یا API Token |
| همگام‌سازی | سینک خودکار inbound ها |
| امتیاز سلامت | امتیاز ۰ تا ۱۰۰ با درجه A تا F |
| تگ‌ها | دسته‌بندی سرورها با تگ سفارشی |
| عملیات دسته‌ای | پینگ، سینک، فعال/غیرفعال چند سرور |

### 📡 مانیتورینگ و اعلان

| قابلیت | توضیح |
|--------|-------|
| TCP Ping | تست اتصال هر اوت‌باند |
| منابع | CPU، RAM، دیسک، وضعیت Xray |
| غیرفعال‌سازی خودکار | بعد از N خرابی متوالی |
| تشخیص تغییر IP | هشدار هنگام تغییر IP سرور |
| محدودیت ترافیک | هشدار در ۸۰٪ و ۱۰۰٪ |
| لحظه‌ای | آپدیت SSE بدون رفرش صفحه |

### 🔔 رخدادها و اعلان‌ها

| قابلیت | توضیح |
|--------|-------|
| چرخه حیات | باز ← تایید ← حل شده |
| تلگرام | ربات اعلان + دستورات دوطرفه |
| Webhook | ارسال event به Zapier، n8n، Make |
| مرورگر | نوتیفیکیشن push برای alert جدید |
| زمان‌بندی | گزارش هفتگی خودکار |

### 📊 گزارش‌دهی و خروجی

| قابلیت | توضیح |
|--------|-------|
| گزارش Uptime | availability سرور در ۷/۳۰/۹۰ روز |
| عملکرد | آمار latency هر اوت‌باند |
| خروجی CSV | سرورها، اوت‌باندها، رخدادها |
| Badge عمومی | سازگار با shields.io |
| مستندات API | OpenAPI 3.0 خودکار |

### 🔐 امنیت

| قابلیت | توضیح |
|--------|-------|
| رمز عبور | PBKDF2-SHA256 (۲۶۰ هزار تکرار) |
| رمزنگاری | AES-256-CBC برای credentials |
| محدودیت نرخ | Login: ۱۰/۱۵دقیقه، API: ۱۲۰/دقیقه |
| نشست | کوکی HttpOnly، انقضای ۷ روزه |
| RBAC | ادمین + ۱۰ مدیر با دسترسی بخشی |
| حسابرسی | لاگ کامل عملیات |
| لایسنس | توکن امضاشده Ed25519 |

### 🎨 داشبورد

| قابلیت | توضیح |
|--------|-------|
| حالت تاریک | تم Dark کامل با تشخیص سیستم |
| RTL | رابط فارسی + پشتیبانی انگلیسی |
| PWA | قابل نصب روی موبایل |
| نمودار | تاریخچه CPU/RAM و پینگ |
| صفحه‌بندی | جستجو، فیلتر و pagination |
| برندینگ | لوگو، رنگ و نام سفارشی |

---

## 🏗 معماری

```
Veltrix/
├── outpanel/              ۲۶ ماژول Python (بک‌اند)
│   ├── app.py             سرور HTTP + router
│   ├── routes.py          ۷۷ endpoint API
│   ├── worker.py          مانیتورینگ پس‌زمینه
│   ├── sse.py             آپدیت لحظه‌ای SSE
│   ├── panels.py          آداپتور چند پنل
│   ├── telegram_bot.py    ربات تلگرام دوطرفه
│   ├── crypto.py          رمزنگاری AES-256
│   ├── reports.py         گزارش‌دهی + CSV
│   └── ...                Auth, licensing, alerts, i18n
├── web/                   فرانت‌اند (Vanilla JS SPA)
├── tests/                 تست‌های واحد (pytest)
├── .github/workflows/     CI/CD
├── scripts/               اسکریپت نصب خودکار
├── docker-compose.yml     استقرار production
└── docs/                  مستندات
```

---

## ⚙️ فناوری

| لایه | فناوری |
|------|--------|
| بک‌اند | Python 3.12+ (فقط stdlib — بدون وابستگی) |
| دیتابیس | SQLite با WAL mode |
| فرانت‌اند | Vanilla JavaScript SPA |
| استایل | CSS سفارشی با Dark Mode |
| کانتینر | Docker + Docker Compose |
| استقرار | سرویس systemd روی Linux |
| CI/CD | GitHub Actions |
| تست | pytest |

---

## 🚀 استقرار

### نصب یک‌خطی (Linux)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/iPmartNetwork/Veltrix/master/scripts/install-linux.sh)
```

اسکریپت نصب شامل:
- 🔍 تشخیص خودکار OS (Ubuntu, Debian, CentOS, Fedora, Arch)
- 🐍 نصب خودکار Python 3.12 در صورت عدم وجود
- 🔑 تولید خودکار کلید رمزنگاری و توکن API
- 🛡 سرویس systemd با تنظیمات امنیتی
- 📋 منوی تعاملی (نصب، آپدیت، دمو، حذف)

### Docker

```bash
docker compose up -d
```

### توسعه محلی

```bash
python -m outpanel.app --host 127.0.0.1 --port 8000
```

---

## 🤖 ربات تلگرام

تنظیم در `.env`:
```env
OUTPANEL_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
OUTPANEL_TELEGRAM_ALLOWED_CHATS=-1001234567890
```

دستورات:
| دستور | توضیح |
|--------|-------|
| `/status` | نمای کلی سرورها |
| `/servers` | لیست سرورها با وضعیت |
| `/server <id>` | جزئیات + متریک سرور |
| `/ping <id>` | تست پینگ اوت‌باندها |
| `/alerts` | اعلان‌های فعال |
| `/incidents` | رخدادهای باز |
| `/health` | امتیاز سلامت |

---

## 📜 لایسنس

Veltrix **نرم‌افزار تجاری اختصاصی** است.

استفاده، نصب، تغییر، توزیع، فروش مجدد، واگذاری، میزبانی عمومی یا در دسترس قرار دادن بدون لایسنس معتبر صادرشده توسط **iPmartNetwork** مجاز نیست.

| پلن | محدودیت | مدت |
|-----|---------|-----|
| Pro | ۲۰ سرور | ۶ ماهه / ۱ ساله / مادام‌العمر |
| Enterprise | ۶۰ سرور + ۶۰ اوت‌باند | ۶ ماهه / ۱ ساله / مادام‌العمر |

---

## 🤝 پشتیبانی

برای خرید لایسنس، پشتیبانی نصب یا استعلام تجاری:

- **GitHub:** [iPmartNetwork](https://github.com/iPmartNetwork)
- **Issues:** [گزارش باگ](https://github.com/iPmartNetwork/Veltrix/issues)

---

<p align="center">
  <img src="img/Veltrix.png" alt="Veltrix" width="120" />
</p>

<p align="center">
  <sub>ساخته شده با دقت توسط <strong>iPmartNetwork</strong></sub><br>
  <sub>© 2026 iPmartNetwork — تمامی حقوق محفوظ است.</sub>
</p>
