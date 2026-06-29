# `scripts/` — Graph Seeding

Operational tooling for the service dependency graph. These scripts are **not**
Azure Functions — they have no trigger and are never exposed by the deployed app.
They run from your laptop or a CI/CD pipeline and talk to Blob Storage over the
network.

## `seed_graph.py`

Validates `BlastRadiusApi/data/services.json` and uploads it to the `graph-data`
container as `services.json`. Run it once per graph change.

```powershell
# Full run: validate, then upload
python scripts/seed_graph.py

# Validate only — no upload. Use this as a CI gate.
python scripts/seed_graph.py --validate-only
```

### What validation checks

- Node `id`s are unique.
- Every edge `source`/`target` references an existing node id.

A dangling edge or duplicate id does **not** fail at upload time — it fails
silently later when the Function runs BFS during a real incident. Validation
turns that into a hard failure (exit code `1`) before anything is written.

### Authentication

`seed_graph.py` uses `DefaultAzureCredential`, so it authenticates the same way
whether it runs on your machine or in a pipeline:

| Target | Set `BlobStorageAccountUrl`? | Identity used |
|---|---|---|
| Real Azure Storage | Yes — `https://<account>.blob.core.windows.net` | Managed Identity / `az login` / CI service principal (needs **Storage Blob Data Contributor**) |
| Local Azurite | No | Falls back to `AzureWebJobsStorage` (`UseDevelopmentStorage=true`) |

> "On Azure" means *authenticating against a real Azure storage account* — not
> running inside the Function host. The script always runs as an external client.

### Seeding production manually

```powershell
$env:BlobStorageAccountUrl = "https://<account>.blob.core.windows.net"
az login
python scripts/seed_graph.py
```

The identity you sign in as must have **Storage Blob Data Contributor** on the
storage account.

## CI/CD

Graph data and function code are **separate lifecycles** — the graph changes when
services/dependencies change, the code changes when logic changes. Keep seeding
out of band so a code-only deploy never rewrites graph data mid-incident.

- **CI (every PR/push):** validate, no upload.
- **CD (on merge/deploy):** upload, ideally only when `services.json` changed.

### GitHub Actions sketch

```yaml
jobs:
  validate-graph:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r BlastRadiusApi/requirements.txt
      - run: python BlastRadiusApi/scripts/seed_graph.py --validate-only

  seed-graph:
    needs: validate-graph
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      id-token: write   # OIDC federated credential
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r BlastRadiusApi/requirements.txt
      - run: python BlastRadiusApi/scripts/seed_graph.py
        env:
          BlobStorageAccountUrl: ${{ vars.BLOB_STORAGE_ACCOUNT_URL }}
```

The `seed-graph` job's federated identity needs **Storage Blob Data Contributor**
on the storage account.
