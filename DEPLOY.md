# Deploying to GitHub + Render (with Neon for the database)

## 1. Create a free Postgres database on Neon

1. Go to https://neon.tech and sign up (free, no card needed).
2. Create a new project - any name is fine.
3. On the project dashboard, copy the **connection string** (looks like
   `postgresql://username:password@ep-xxxx.neon.tech/dbname?sslmode=require`).
   Keep this safe - you'll paste it into Render in step 4.

## 2. Push this project to GitHub

From inside the `smart_village` folder:

```
git init
git add .
git commit -m "Initial commit"
```

Then create a new empty repository on https://github.com/new (don't add a README/license
there - you already have files), and run the two commands GitHub shows you, e.g.:

```
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

**Before you push:** double check `backend/config.py` still has the placeholder text
(`PUT_YOUR_..._HERE`), not your real API keys - real keys belong in `.env` (local) or
Render's dashboard (deployed), never in a file that gets committed. The `.gitignore`
already included in this project keeps `.env` out of git for you.

## 3. Deploy on Render using the included blueprint

1. Go to https://dashboard.render.com, sign up/log in (free, no card needed for this).
2. Click **New > Blueprint**.
3. Connect your GitHub account and select the repo you just pushed.
4. Render will find `render.yaml` in the repo root and show two services:
   `smart-village-backend` and `smart-village-frontend`.
5. It will prompt you to fill in three environment variables for the backend:
   - `DATABASE_URL` - paste the Neon connection string from step 1
   - `WEATHER_API_KEY` - your OpenWeather key
   - `GEMINI_API_KEY` - your Gemini key
6. Click **Apply**. Render builds and deploys both services (a few minutes).
7. Once done, copy the backend's URL, e.g. `https://smart-village-backend.onrender.com`.

## 4. Point the frontend at the real backend URL

Open `frontend/script.js`, find this line near the top:

```js
const API_URL = "http://127.0.0.1:8000";
```

Replace it with your actual Render backend URL from step 3.7, then:

```
git add frontend/script.js
git commit -m "Point frontend at deployed backend"
git push
```

Render automatically redeploys the frontend static site with the update.

## 5. Test it

Visit your frontend's Render URL (e.g. `https://smart-village-frontend.onrender.com`).
Try registering a worker account, posting a job as an employer, and applying to it -
this confirms the whole chain (frontend -> Render backend -> Neon database) is working.

## Things to know about the free tiers

- **Cold starts**: Render's free web services sleep after 15 minutes of no traffic and
  take about a minute to wake back up on the next request. The first request after a
  quiet period will feel slow - that's expected, not a bug.
- **750 free instance-hours/month**: plenty for a student project; resets monthly.
- **Neon's free database has no expiry** (unlike Render's own free Postgres, which
  expires after 30 days) - this is why the database lives on Neon specifically.
- If you ever see database connection errors after a long period of inactivity, it's
  usually the backend waking up from sleep - wait ~60 seconds and retry.
