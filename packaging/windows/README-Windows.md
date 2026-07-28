# PanelScout for Windows

## Run

1. Download `PanelScout-*-windows-x64.zip`.
2. Extract the zip to a normal folder such as `Downloads\PanelScout`.
3. Double-click `PanelScout.exe`.
4. Keep the console window open while using the app. PanelScout opens the local UI in your default browser.

PanelScout runs only on `127.0.0.1`. Log in from the UI with your own account for the current use session, search comics, pick chapters, choose a download folder, and confirm download.

## Local Data

By default, PanelScout stores local data under the current Windows user profile:

- Config: `%USERPROFILE%\.config\panelscout\config.toml` when you create one manually.
- Database and auth session: `%USERPROFILE%\.local\share\panelscout`.
- Cache: `%USERPROFILE%\.cache\panelscout`.
- Default downloads: `%USERPROFILE%\Downloads`.

Passwords are not saved by PanelScout. The saved browser session is local to the Windows user profile.

## Troubleshooting

- If Windows SmartScreen warns about the app, choose the extra details option and run it only if the zip came from this project's release page. The first release is unsigned.
- If the browser does not open, visit `http://127.0.0.1:8765/` manually while `PanelScout.exe` is running.
- If port `8765` is already in use, start from PowerShell with another port:

```powershell
.\PanelScout.exe --port 8766
```

- If login or chapter rendering fails, close all PanelScout windows, restart `PanelScout.exe`, log in again, and retry.
