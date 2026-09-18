# Tradex Academy

A full-featured institutional trading academy and multi-tier subscription platform built with Django.

## 🚀 Key Features

- **Multi-Tier Curriculum Access**:
  - **Standard Academy (₹5,000 / 60 days)**: Spot Gold fundamentals & Indian Market (Futures, Options Greeks, Stock Price Action).
  - **Forex Gold Strategy & Strategy Indicator (₹10,000 / 60 days)**: Proprietary institutional Gold Strategy based on pure price action + custom Strategy Indicator (PineScript/MT5) and London Killzone scalping framework.
  - **Combined Master Access (₹12,500 / 150 days)**: Extended 5-month access to all courses + exclusive **VIP Community** trade setup channels.
- **Payment & Subscriptions**:
  - Razorpay payment gateway integration with secure signature verification.
  - Built-in mock payment simulator for seamless local development and testing.
  - Real-time validity countdown, expiry management, and payment history dashboard.
- **VIP Community Hub**:
  - Telegram-style structured channels for Mentor Announcements, High-Probability Trade Setups, and Live Trading Discussions.
- **Video Lesson Player**:
  - Responsive video streaming with progress tracking and completion state.
- **Custom Authentication**:
  - Email-based login backend (`EmailAuthBackend`), user profile management, password updates, and referral system.

---

## 🛠️ Tech Stack

- **Backend**: Python, Django 6.0
- **Database**: SQLite (default for development) / MySQL (production ready)
- **Payment Gateway**: Razorpay
- **Styling**: Modern Vanilla CSS Design System with dark/light themes and Lucide icons

---

## 📦 Quick Setup

### 1. Clone the repository
```bash
git clone https://github.com/vishvam5379/Tradex_Academy.git
cd Tradex_Academy
```

### 2. Set up virtual environment & install dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 4. Run database migrations & seed initial data
```bash
python manage.py migrate
python manage.py seed_courses
```

### 5. Start the development server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🔑 Demo User Credentials (from `seed_courses`)

| Role / Plan | Email | Password |
| :--- | :--- | :--- |
| **Combo Master (5 Months + Community)** | `pro_trader@example.com` | `Trader@123` |
| **Gold Strategy & Indicator** | `gold_trader@example.com` | `Gold@123` |
| **Standard Academy** | `standard_trader@example.com` | `Standard@123` |
| **Free Account** | `free_user@example.com` | `Free@123` |
| **Admin** | `admin@tradingacademy.com` | `Admin@123456` |

---

## 🧪 Running Tests

```bash
python manage.py test
```
