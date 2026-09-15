# Alpha Kappa Psi · Rho Chi Member Portal

Chapman University chapter portal with the current navy-and-gold design.

## Upload to GitHub

Create a repository (a private repository is recommended), extract the accompanying ZIP, and upload the **contents** of this folder. Include the hidden `.gitignore` and `.env.example` files. Do not upload the ZIP itself as the website source.

This package includes the website code only. No member directory, attendance records, spreadsheet snapshots, access allowlist, credentials, or databases are included.

## Run locally

Requires Python 3.12 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 run.py
```

On Windows, activate with `.venv\Scripts\activate` instead.
Open http://127.0.0.1:8765/ . The first run creates `.env` and an empty local demo snapshot in `private/`. The layout works with empty data until Sheets are configured.

## Connect the chapter spreadsheets

Edit `.env` locally. Set `HUB_ACT_SHEET_ID`, `HUB_RUSH_SHEET_ID`, and `HUB_CAL_SHEET_ID` to the IDs from the actives, rush, and calendar Google Sheets URLs (the text between `/d/` and `/edit`). Set `HUB_AUTO_SYNC=1` and restart. Export sync requires existing link-readable access; this program does not change sharing settings. Set `HUB_PREVIEW_EMAIL` to the roster email whose record you want to preview locally.

Preview grants officer access and is for local use only. Source snapshots, website edits, and member allowlists belong in ignored `private/`, never in GitHub. The existing source sheets must retain their expected tabs and layout.

## Member login

For real login, configure a Google OAuth web client and enable the Sheets API. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `HUB_ORIGIN`. Register `HUB_ORIGIN/auth/callback` as the redirect URI. Set `HUB_PREVIEW=0`.

Create `private/members.json` containing an array of approved lowercase Google emails. Set `HUB_OFFICER_EMAILS` to the approved comma-separated officer emails. Members need access to the source sheets. Real OAuth credentials and sign-in still need end-to-end verification before launch.

## Hosting

Uploading to GitHub stores the code; it does not publish a working member portal. **GitHub Pages cannot run this Python backend.** Online launch requires a Python-capable host, HTTPS, persistent private storage, and production server configuration. The bundled server binds to localhost. Do not expose preview mode publicly.

## Features

- Home with the compact next-event card and original chapter card
- Calendar, member directory, buddy pairings, academic resources
- Attendance grouped by category, status colors, and event point estimates
- Compact tabling assignments and consistent date labels
- Officer announcements and event edits, plus member feedback
- Optional automatic read-only Sheets sync

Overall points use the spreadsheet total. Event points are derived from available policy values; ambiguous values remain pending. Category caps and adjustments may make totals differ. Yearless source dates currently use the Fall 2026 season.

## Files

`public/` contains the interface. `server.py` handles authentication and requests. `data_provider.py` reads and normalizes Sheets. `sheets_sync.py` refreshes local snapshots. `store.py` stores website edits in SQLite. `run.py` loads local configuration and launches the server.
