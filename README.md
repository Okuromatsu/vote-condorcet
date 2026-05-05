# Condorcet Vote 🗳️

A fair and transparent voting system using the Condorcet method - no registration required, just rank and vote!

Online public version here : ([vote-condorcet.com](https://vote-condorcet.com/en/))

## ✨ Features

- **Fair Voting** - Condorcet method finds the candidate who beats all others in head-to-head matchups
- **Ranked Choice** - Voters rank candidates by preference (1st, 2nd, 3rd, etc.)
- **Automatic Results** - System calculates winner using pairwise comparisons
- **Easy Sharing** - Unique URLs and QR codes for poll distribution
- **Duplicate Prevention** - Cookie-based fingerprinting prevents vote manipulation
- **No Account Required** - Simple, accessible, anonymous voting
- **Multi-language** - Support for French (FR), Spanish (ES), and English (EN)

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Git

### Setup (5 minutes)

```bash
# Clone repository
git clone https://github.com/yourname/condorcet-vote.git
cd condorcet-vote

# Create virtual environment
python -m venv .venv
source ./venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Setup database
python manage.py migrate

# Create admin user (optional)
python manage.py createsuperuser

# Run server
python manage.py runserver
```

Visit: http://localhost:8000/

## 📖 How It Works

1. **Create Poll** - Enter title, candidates, optional description
2. **Share Link** - Get unique URL to share with voters
3. **Vote** - Voters rank all candidates by preference
4. **Results** - System calculates Condorcet winner automatically

### The Condorcet Method
- Compares each candidate against every other candidate head-to-head
- Winner is candidate who beats all others in one-on-one matchups
- If tie exists, Schulze tiebreaker method is used

**Example:**
```
Voters rank: Python > JavaScript > Java
            JavaScript > Java > Python
            Java > Python > JavaScript

Matchups:
- Python vs JavaScript: 2 wins → Python wins
- Python vs Java: 2 wins → Python wins
- JavaScript vs Java: 1 win, 1 loss → Tie

Result: Python is Condorcet winner (beats all others)
```

## 🏗️ Project Structure

```
condorcet-vote/
├── voting/                 # Main app
│   ├── models.py          # Database models
│   ├── views.py           # Business logic
│   ├── forms.py           # Form validation
│   ├── utils.py           # Voting algorithm
│   ├── templates/         # HTML templates
│   └── static/            # CSS/JavaScript
├── condorcet_project/     # Django settings
├── locale/                # Translation files (FR, ES)
├── manage.py              # Django CLI
├── requirements.txt       # Dependencies
└── README.md             # This file
```

## 🔧 Configuration

### Development (Default)
```bash
python manage.py runserver
# DEBUG=True, SQLite database, no security restrictions
```

### Production

1. Set environment variables (or `.env` file):
   - `SECRET_KEY` - Django secret (generate new one)
   - `DEBUG` - Set to `False`
   - `ALLOWED_HOSTS` - Your domain(s)

2. Run migrations:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

3. Use Gunicorn:
```bash
gunicorn condorcet_project.wsgi:application --bind 0.0.0.0:8000
```

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run specific app
python manage.py test voting
```

## 🌐 Translations

Currently supported:
- 🇬🇧 English (EN) - Default
- 🇫🇷 Français (FR) - Complete
- 🇪🇸 Español (ES) - Complete

### Add New Translation
```bash
python manage.py makemessages -l [lang_code]
# Edit locale/[lang_code]/LC_MESSAGES/django.po
python manage.py compilemessages
```
## 📦 Dependencies

See `requirements.txt` for complete list. Main packages:
- **Django 4.2.7** - Web framework
- **Bootstrap 5** - Frontend styling
- **PostgreSQL** - Production database (optional, defaults to SQLite)
- **Gunicorn** - Production server

## 📝 License

CC BY-NC-SA 4.0
