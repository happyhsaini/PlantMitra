# PlantMitra backend (Phase 1)

Run from this folder so `.env` and the `app` package resolve correctly.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
