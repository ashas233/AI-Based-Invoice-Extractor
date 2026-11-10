# Invoice Extractor (multimodal GenAI)

Upload an invoice (PDF, scan, or phone photo) and get validated, structured JSON with a human-review UI and CSV/Excel export.

```
Upload -> preprocess (PDF->images, rotate, contrast) -> vision LLM -> Pydantic schema
       -> math/business validation -> self-correction loop -> review UI -> SQLite -> CSV/Excel
```

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows PowerShell: Copy-Item .env.example .env
# Edit .env and replace the ANTHROPIC_API_KEY placeholder with your real key.
uvicorn app.main:app --reload                          # terminal 1 (API on :8000)
streamlit run ui/streamlit_app.py                      # terminal 2 (UI on :8501)
```
Docker: `docker compose up --build`

For a no-key walkthrough, open the UI and select **Try free sample demo**.
It loads simulated sample invoice data for review and saving; it does not
process uploaded documents or call an AI provider. Uploaded invoice extraction
still requires an `ANTHROPIC_API_KEY`.

## Free public demo on Hugging Face Spaces

The free public sample-only demo is live at
https://huggingface.co/spaces/ashas2345/invoice-extractor-free-demo. It uses
the standalone page in `static_demo/index.html`, so it does not need a compute
server, API key, or account to try. The public Space source is visible. This
static preview does not accept invoice uploads, call AI, or save data.

Hugging Face currently marks Spaces that run Docker or Gradio as requiring a
paid plan; static Spaces are available for free. Do not upload `.env` files,
API keys, real invoices, or the local `data/` folder to a public Space.

## Deploy to Azure and GitHub

The prepared deployment uses Azure Container Apps, an Azure Files share for
persistent SQLite data, and Azure Container Registry. The API and Streamlit UI
run as containers in one app; only the UI port is exposed. The app is private
by default. Public access is enabled only with Microsoft Entra ID sign-in,
restricted to the configured user's Entra object ID.

The target repository `https://github.com/ashas233/generative-aI-` is empty.
After installing Git and authenticating with GitHub, push this project from
its directory:

```bash
git init -b main
git add .
git commit -m "Initial invoice extractor app"
git remote add origin https://github.com/ashas233/generative-aI-.git
git push -u origin main
```

Before deploying, create an Azure resource group and a GitHub Actions
service principal configured for OIDC federation to this repository's `main`
branch. For example, after creating the resource group, create the app and
service principal, then add a federated credential:

```bash
CLIENT_ID=$(az ad app create \
  --display-name github-invoice-extractor \
  --query appId -o tsv)
az ad sp create --id "$CLIENT_ID"
az ad app federated-credential create --id "$CLIENT_ID" --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:ashas233/generative-aI-:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_GROUP="<your-resource-group>"
OBJECT_ID=$(az ad sp show --id "$CLIENT_ID" --query id -o tsv)
SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
az role assignment create \
  --assignee-object-id "$OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$SCOPE"
az role assignment create \
  --assignee-object-id "$OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Role Based Access Control Administrator" --scope "$SCOPE"
```

Give that service principal `Contributor` and `Role Based Access Control
Administrator` roles on the resource group. The workflow creates ACR
push/pull role assignments, so its identity needs permission to assign those
roles. Set `AZURE_DEPLOYER_OBJECT_ID` to the service principal's object ID,
not the client ID.

Add these GitHub Actions **secrets**:

- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`: the GitHub
  Actions OIDC identity.
- `ANTHROPIC_API_KEY`: the API key used for invoice extraction.

Add these GitHub Actions **variables**:

- `AZURE_RESOURCE_GROUP`: the existing resource group name.
- `AZURE_LOCATION`: an Azure region that supports Container Apps.
- `AZURE_NAME_PREFIX`: 3-8 lowercase letters or digits, unique within the
  Azure subscription.
- `AZURE_DEPLOYER_OBJECT_ID`: the service principal's object ID (not its
  client ID).

Push the workflow and project to `main`, then run **Actions → Deploy to Azure
Container Apps → Run workflow**. The first run provisions resources and keeps
the app private. It prints the app URL; it does not enable public access.

To enable public access, register an Entra ID application with this redirect
using single-tenant accounts and add a Web redirect URI, replacing `<app-url>`
with the URL printed by the workflow:

```text
<app-url>/.auth/login/aad/callback
```

Create a client secret for that Entra application and add these GitHub
Actions secrets: `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET`,
and `ENTRA_ALLOWED_USER_OBJECT_ID` (the allowed user's Entra object ID). Run
the workflow again with **enable_public_access** selected. The workflow first
applies authentication while ingress remains private, then exposes the app.

The SQLite database and vendor index persist on Azure Files. Existing local
data in `data/` is not uploaded or migrated; the deployed database starts
empty. The workflow is manual to avoid provisioning Azure resources
automatically on every push. No GitHub push or Azure provisioning was
performed while preparing these files.

## Database configuration
Local development uses SQLite by default (`DB_BACKEND=sqlite`). For a durable
PostgreSQL deployment instead of the Azure Files-backed SQLite setup, set
`DB_BACKEND=postgres` and configure `DB_HOST`, `DB_NAME`, `DB_USER`, and
`DB_PASSWORD` for your PostgreSQL server. Keep `DB_PASSWORD` in a secret
manager rather than in a checked-in environment file. See `.env.example` for
the local configuration template.

## Evaluate
```bash
python eval/make_synthetic.py 30     # synthetic PDFs + ground truth
python eval/run_eval.py              # prints the metrics table
pytest                               # unit tests for validators
```
Add your own real, messy invoices (photos, skewed scans, Urdu/English) with matching `.json` labels to `eval/dataset/`.

## Results
(Paste your measured table from `run_eval.py` here.)

## Design decisions / limitations
- Never trust model arithmetic: totals are re-checked in code, and failures trigger one self-correction pass.
- Missing fields are null, not guessed.
- Vendor normalization uses FAISS embeddings; threshold is tunable and can merge similar-named vendors.
- Duplicate detection: same canonical vendor + invoice number + total.
- Not handled yet: handwritten invoices, >8 pages, multi-invoice PDFs.
