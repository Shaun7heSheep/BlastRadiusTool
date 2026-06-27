# Local Settings Configuration Guide

This document explains each setting in `local.settings.json` and how to configure them for different scenarios.

## Settings Overview

### `FUNCTIONS_WORKER_RUNTIME` (Required)
- **Value**: `python`
- **Purpose**: Tells Azure Functions Core Tools that this is a Python project
- **Don't change this**

### `AzureWebJobsStorage` (Required)
Storage account connection string for Blob Storage and Function state.

#### Option 1: Local Development with Azurite (Recommended for Phase 7 E2E)
```json
"AzureWebJobsStorage": "UseDevelopmentStorage=true"
```
- Uses the local Azurite emulator (localhost:10000)
- Requires: `azurite --silent` running in another terminal
- No Azure resources needed
- Azurite requires `--skipApiVersionCheck` because azure-storage-blob SDK v12.30.0 sends API version 2026-06-06 which Azurite 3.35.0 doesn't natively support

#### Option 2: Real Azure Storage Account
```json
"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=blastradius;AccountKey=YOUR_STORAGE_ACCOUNT_KEY_HERE;EndpointSuffix=core.windows.net"
```
- Get the connection string from Azure Portal → Storage Account → Access Keys
- Copy the full connection string, keep it secret, never commit it

### `AzureSignalRConnectionString` (Required for real-time broadcasts)
SignalR Service connection string for broadcasting blast radius results to connected clients.

#### Option 1: Mock/Local Development (No Broadcast)
```json
"AzureSignalRConnectionString": "Endpoint=https://mock-signalr.service.signalr.net;AccessKey=mock-access-key;Version=1.0"
```
- Broadcasts will fail silently (fire-and-forget pattern)
- UI still renders the graph and can fetch the blast result
- Useful for testing graph logic without Azure SignalR

#### Option 2: Real Azure SignalR Service
```json
"AzureSignalRConnectionString": "Endpoint=https://blastradius-signalr.service.signalr.net;AccessKey=YOUR_SIGNALR_ACCESS_KEY_HERE;Version=1.0"
```
- Get from Azure Portal → SignalR Service → Keys
- Enables real-time broadcast to all connected Blazor clients
- SignalR broadcasts are fire-and-forget; failures don't break the HTTP response

### `BlobStorageAccountUrl` (Optional but Recommended for Azure)
Direct URL to your Blob Storage account. Used with Managed Identity on Azure.

#### Option 1: Local Development with Azurite
```json
"BlobStorageAccountUrl": ""
```
- Leave empty (fallback to `AzureWebJobsStorage`)
- `function_app.py` prefers Managed Identity if this is set

#### Option 2: Local Development with Real Storage
```json
"BlobStorageAccountUrl": "https://blastradius.blob.core.windows.net"
```
- Combined with `DefaultAzureCredential` for Managed Identity auth
- Requires Azure CLI login: `az login`

#### Option 3: Azure Deployment
```json
"BlobStorageAccountUrl": "https://your-storage-account.blob.core.windows.net"
```
- Function's Managed Identity must have `Storage Blob Data Contributor` role
- `function_app.py` will use this URL with `DefaultAzureCredential()`

## CORS Settings

### `Host.CORS`
Comma-separated list of allowed origins for CORS:
```json
"CORS": "http://localhost:5178,https://localhost:7206"
```
- `localhost:5178` — Blazor dev server (HTTP)
- `localhost:7206` — Blazor dev server (HTTPS)
- On Azure: Add your Static Web App URL, e.g., `https://your-app.azurestaticapps.net`

### `Host.CORSCredentials`
```json
"CORSCredentials": true
```
- Allows credentials (cookies, auth headers) in CORS requests
- Needed for SignalR token-based auth

## Quick Start Scenarios

### Scenario 1: Local E2E with Azurite (Phase 7)
```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "AzureSignalRConnectionString": "Endpoint=https://mock-signalr.service.signalr.net;AccessKey=mock;Version=1.0",
    "BlobStorageAccountUrl": ""
  },
  "Host": {
    "CORS": "http://localhost:5178,https://localhost:7206",
    "CORSCredentials": true
  }
}
```
**Setup**:
1. `azurite --silent` in one terminal
2. `cd BlastRadiusApi && python scripts/seed_graph.py` to populate the graph
3. `func start` to run the Function locally
4. `dotnet watch --project BlastRadiusUI` in another terminal

### Scenario 2: Local with Real Azure Resources
```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "<your-storage-connection-string>",
    "AzureSignalRConnectionString": "<your-signalr-connection-string>",
    "BlobStorageAccountUrl": "https://your-storage-account.blob.core.windows.net"
  },
  "Host": {
    "CORS": "http://localhost:5178,https://localhost:7206",
    "CORSCredentials": true
  }
}
```
**Setup**:
1. Create a Storage Account in Azure
2. Create a SignalR Service in Azure
3. Copy connection strings from Azure Portal
4. `az login` for Managed Identity auth
5. Run locally as above

### Scenario 3: Azure Production Deployment
When deploying to Azure Functions + Static Web Apps:
- Store these as **Application Settings** (not in committed files)
- Azure Portal → Function App → Configuration → Application settings
- Use **Managed Identity** — don't put connection strings in `local.settings.json` on the server

## Security Notes

- **Never commit real connection strings** to this repository
- `local.settings.json` is in `.gitignore` — always use `local.settings.json.example` for defaults
- For Azure: Use **Managed Identity** (DefaultAzureCredential) instead of connection strings
- SignalR broadcasts are fire-and-forget; even if SignalR fails, the HTTP response succeeds
- Function key auth is handled by `auth_level=func.AuthLevel.FUNCTION` in `function_app.py`

## Troubleshooting

**SignalR broadcast failing?**
- Check `AzureSignalRConnectionString` format: `Endpoint=...;AccessKey=...;Version=1.0`
- Verify endpoint and key from Azure Portal
- Check Function logs: `func start --verbose`

**Blob Storage not found?**
- If using Azurite: Make sure `azurite --silent` is running
- If using Azure: Verify `AzureWebJobsStorage` or `BlobStorageAccountUrl` is correct
- Run `python scripts/seed_graph.py` to create the `graph-data` container and `services.json`

**CORS errors in browser?**
- Add your Blazor origin to `Host.CORS`
- Verify `CORSCredentials: true`
- Check Function logs for the exact origin being rejected

**Managed Identity errors?**
- For local dev, use `DefaultAzureCredential` with `az login`
- For Azure, assign the Function App's managed identity the required roles in Azure Portal
