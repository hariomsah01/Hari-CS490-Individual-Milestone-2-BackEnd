# Sakila Flask Server

Flask + SQLAlchemy backend for the Sakila DVD store.

## Quickstart
```bash
python -m venv .venv
# PowerShell: .\.venv\Scripts\Activate.ps1
# Git Bash: source .venv/Scripts/activate   # mac/linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your MySQL creds
flask --app app run
```
API base: `http://localhost:5000/api`
