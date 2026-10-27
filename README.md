# PlantMitra (Phase 1)

PlantMitra is a full-stack medicinal-plant companion with a Next.js frontend, FastAPI backend, PostgreSQL database support, image observations, and a seven-class plant-identification model.

## Local development

Prerequisites: Node.js 18+, Python 3.11+, and PostgreSQL or SQLite.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -r ..\ml\requirements-inference.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and replace `JWT_SECRET` with a long random value. Then start the API:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: <http://127.0.0.1:8000/docs>  
Health check: <http://127.0.0.1:8000/health>

### Frontend

In another terminal:

```powershell
cd frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>. Create an account from the signup page; the project no longer creates shared demo accounts.

## Production deployment

The backend Blueprint is in `render.yaml`. It expects a PostgreSQL `DATABASE_URL`, a frontend origin in `CORS_ORIGINS`, and generates a private `JWT_SECRET`. The frontend is a standard Next.js project in `frontend/` and can be deployed separately.

Free Render web services can sleep when idle. For persistent database storage, use an external PostgreSQL service; do not use the local SQLite file in a cloud deployment.

## Model and dataset attribution

The seven-class model was trained using the DIMPSAR medicinal-plant dataset, licensed under CC BY 4.0. The project includes a trained checkpoint and metadata, but no source dataset images.

Pushpa, B. R., & Rani, S. (2023). *DIMPSAR: Dataset for Indian medicinal plant species analysis and recognition*. Data in Brief, 49, 109388. Dataset: [Project-AgML DIMPSAR mirror](https://huggingface.co/datasets/Project-AgML/DIMPSAR_medicinal_plant_classification). License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Model outputs are assistive predictions, not medical diagnoses. Species predictions are not guaranteed to be correct.
