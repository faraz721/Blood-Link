# BLOODLINK
**Find Blood. Save Lives.**

A production-style blood donor platform for **Talagang District** and **Chakwal District** only.

---

## Features

- Find available blood donors by blood group, district and village
- Donor registration & secure login (phone + password)
- Donor dashboard & profile management (availability, WhatsApp, phone update)
- Global floating **AI Help** (RAG-powered) – answers in English, Urdu, Roman Urdu or Punjabi
- Global **Report a Problem** form
- Full Admin panel (live stats, donor management, suspend/unsuspend/delete, reports)
- Responsive design (desktop + mobile hamburger menu)
- Secure: password hashing, rate limiting, session protection, server-side authorization

---

## Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Frontend   | HTML5, CSS3, Vanilla JavaScript     |
| Backend    | Python, Flask                       |
| Database   | PostgreSQL (Supabase Free recommended) |
| AI / RAG   | Local TF-IDF retrieval + configurable LLM |
| Deployment | Render Free Web Service             |

---

## Folder Structure

```
bloodlink/
├── app.py
├── requirements.txt
├── Procfile
├── .env.example
├── .gitignore
├── README.md
├── config/settings.py
├── routes/          (auth, donor, search, admin, reports, ai)
├── models/          (user, donor, location, report, admin, login_attempt)
├── services/        (auth, phone, rag, ai)
├── knowledge_base/  (blood_donation_guide.pdf)
├── data/locations.json
├── templates/
├── static/
├── scripts/         (seed, create_admin, build_rag_index)
└── tests/
```

---

## Local Setup (Windows PowerShell)

### 1. Clone / Extract
```powershell
cd path\to\bloodlink
```

### 2. Create virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Environment variables
```powershell
copy .env.example .env
```
Edit `.env` and set at least:
- `SECRET_KEY` (long random string)
- `DATABASE_URL` (Supabase connection string – see below)
- `AI_API_KEY` (optional – for live AI answers)
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`

### 5. Database (Supabase)
1. Create free account at https://supabase.com
2. Create a new project
3. Go to **Project Settings → Database** → copy the **URI** connection string
4. Paste into `.env` as `DATABASE_URL=postgresql://postgres:...@db.xxx.supabase.co:5432/postgres`
5. Run:
```powershell
python -c "from app import create_app; from models import db; app=create_app(); app.app_context().push(); db.create_all(); print('Tables created')"
python scripts/seed_locations.py
python scripts/create_admin.py
```

### 6. Build RAG index
```powershell
python scripts/build_rag_index.py
```
(Replace `knowledge_base/blood_donation_guide.pdf` with your real PDF first if desired.)

### 7. Run locally
```powershell
python app.py
```
Open http://127.0.0.1:5000

---

## AI Help – Multi-language Support

Users can ask questions in:
- English
- Urdu (Arabic script)
- Roman Urdu
- Punjabi (Shahmukhi or Roman)

The AI detects the language of the question and replies in the **same language**.  
System prompt enforces: answer only from retrieved knowledge-base context; never invent medical facts.

---

## Village Data

Villages are loaded from `data/locations.json` (curated list sourced primarily from Wikipedia “List of villages in Talagang/Chakwal District”).  
The list is **not claimed as a complete official PBS Mouza Census extract**.  
Village field is a **dropdown only** – free text is never accepted.  
Selecting a district filters the village list accordingly.

---

## Admin

After running `scripts/create_admin.py`:
- Go to `/admin/login`
- Use the username/password from your `.env`

---

## Deployment (GitHub → Render)

1. Push the project to a GitHub repository (**do not commit `.env`**).
2. On https://render.com create a **Web Service**.
3. Connect the GitHub repo.
4. Settings:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add environment variables (same as `.env`):
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` (optional)
   - `ADMIN_USERNAME`, `ADMIN_PASSWORD` (for bootstrap)
6. Deploy.
7. After first deploy, open a Render Shell and run:
   ```
   python scripts/seed_locations.py
   python scripts/create_admin.py
   python scripts/build_rag_index.py
   ```

---

## Known Free-Tier Limitations

- **Render Free Web Service** spins down after ~15 minutes of inactivity. The first request after sleep will take longer (cold start). The app still works normally after waking.
- Do **not** implement artificial self-pinging to bypass platform limits.
- Prefer **Supabase Free PostgreSQL** over Render Free Postgres (Render free Postgres expires after 30 days).

---

## Security Notes

- Passwords are hashed (Werkzeug).
- Login throttling / temporary lockout after repeated failures.
- Generic error messages on failed login.
- Admin and donor sessions are separate.
- Authorization is enforced server-side on every protected route.
- Suspended donors cannot log in and never appear in public search.
- API keys and secrets stay in environment variables only.

---

## Testing Checklist (quick)

- [ ] Home loads (desktop + mobile)
- [ ] Register donor (validation, duplicate phone)
- [ ] Login / Logout / session persists
- [ ] Profile update (phone, WhatsApp same-as-phone, availability)
- [ ] Search filters + suspended donors hidden
- [ ] Report form + admin can view/mark/delete
- [ ] Admin dashboard live counts
- [ ] Suspend / Unsuspend / Delete donor
- [ ] AI Help (English + Urdu/Roman questions)
- [ ] Unauthorized access blocked

---

## License

This is a portfolio / community project. Use responsibly.
