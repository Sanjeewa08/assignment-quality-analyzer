# Azure backend and Vercel frontend

The Flask application remains the analysis/authentication API; `frontend/` is the separately hosted Vercel site. The Vercel rewrite sends `/api/*` to Azure, so browser requests and the Flask session cookie remain same-origin from the browser's perspective.

## 1. Deploy the API to Azure Container Apps

Create an Azure Database for PostgreSQL Flexible Server and an Azure Container Apps environment. Keep the database private where possible and configure network access from the Container Apps environment. Use a single database for persistent accounts, rubrics, and submission history; the container filesystem is not a persistent database.

From the project root, build and deploy the Dockerfile (Azure CLI and Container Apps extension required):

```powershell
az login
az containerapp up --name aqa-api-<unique-name> --resource-group <resource-group> --location <azure-region> --source . --ingress external --target-port 7860
```

In the Container App's **Secrets** and **Environment variables** settings, configure:

| Variable | Value |
|---|---|
| `AQA_SECRET_KEY` | A newly generated, long random secret; do not use the development fallback |
| `AQA_COOKIE_SECURE` | `true` |
| `AQA_CSRF_SSL_STRICT` | `false` (the HTTPS request is proxied, so its browser Referer host differs from the Azure API host; CSRF tokens remain required) |
| `DATABASE_URL` | `postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require` |
| `PORT` | `7860` |

URL-encode special characters in the database username/password. Keep the database URL and secret key in Azure secrets, not in source control. The backend health check is `https://<container-app-fqdn>/health`. The first app startup creates the database tables. The API supports the same 10 MB upload limit as the local app.

If needed, create a lecturer account from an authenticated Container App console using:

```powershell
python -m flask --app run.py create-lecturer
```

## 2. Point Vercel at the Azure API

Create a Vercel project from this GitHub repository and set its **Root Directory** to `frontend`. In `frontend/vercel.json`, replace `replace-with-your-container-app-fqdn.azurecontainerapps.io` with the exact Azure Container App hostname. Vercel redeploys the static frontend and routes `/api/*` calls to that backend.

Check the deployed frontend can reach `/api/csrf`, register a student account, upload a small `.txt` file, open its report, and download the PDF. Do not share production student files until database backup, retention, privacy notice, HTTPS, and institutional review are in place.

## Notes

- The web UI and API both use Flask's server-side session auth and CSRF tokens. Keep API calls on the Vercel `/api/*` proxy path; calling Azure directly from browser code bypasses the intended same-origin cookie setup.
- PostgreSQL is recommended for hosted data. SQLite in a container's writable layer is ephemeral and unsuitable for production or multiple replicas.
- The similarity comparison is limited to this app's local database and any reference passage supplied by the user. It is not an internet plagiarism search. AI-style signals are not authorship evidence.
