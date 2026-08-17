# AGENTS.md

KVM-over-USB: control a headless PC (video + keyboard/mouse) over USB using an MS2130 capture card (video) and a CH340+CH9329 serial line emulating USB HID. This repo is a fork of ElluIFX/KVM-Card-Mini-PySide6 with `hid_def.py` rewritten from USB HID to CH9329 serial protocol. Windows-only client.

## Repo layout

- `client/` — the entire Python/PySide6 application (everything else is docs/assets)
- `drivers/CH341SER/` — vendored CH340 Windows driver installers (SETUP.EXE); binary, do not modify
- `image/` — README assets only

## Run (dev)

```
cd client
python Mini-KVM.py debug
```

- Entry chain: `Mini-KVM.py` (exception wrapper, writes `error.log` next to exe/script) → `main.py:main()`
- The trailing `debug` argv is REQUIRED to see output: without it, `print` is stubbed out and loguru/stdout are redirected into an in-app UI buffer (`main.py` ~line 93). With it, `hid_def.set_verbose(True)` is enabled.
- Real COM hardware is needed for keyboard/mouse; without the CH9329 line the app opens a settings dialog at startup. Video works with any UVC capture card.

## Dependencies — requirements.txt is incomplete

`client/requirements.txt` is missing `pyserial` (imported by `hid_def.py`; `numpy` is listed in README but actually unused). The `ch9329` package is NOT on PyPI anymore (README stale): it is vendored locally at `client/ch9329/` (implements exactly the API `hid_def.py` calls; `config.py` retries because the dongle occasionally replies checksum-error frames). Use a China mirror for pip; direct PyPI times out. A working dev venv (Python 3.10) exists at `client/venv`.

## Architecture notes

- `client/hid_def.py` has import-time side effects: it reads/creates `config_hid.yaml` next to `sys.argv[0]` and opens the COM port (9600 baud) at module import. Config file location depends on how the app is launched (script dir vs exe dir). Same for `config.yaml` in `main.py`.
- `client/ui/*_ui.py` are GENERATED from the matching `.ui` files (Qt UI Compiler 6.5.3 header warning). Never hand-edit them; edit the `.ui` and regenerate with `pyside6-uic`.
- `client/web/` is served by `server.py` (Flask, auth, websocket) and `client/web_s/` by `server_simple.py` (plain static http.server, binds 127.0.0.1:5020+, auto-increments if busy).
- `_cpyHook.cp39-win_amd64.pyd` is a Python-3.9-x64 compiled pyWinhook module → the frozen build is pinned to Python 3.9 64-bit.

## Windows filename case gotcha

`hid_def.py` opens `data/KEYBOARD_CH9329CODE2KEY.yaml` (uppercase) but the actual file is `data/keyboard_ch9329code2Key.yaml`. Works only on case-insensitive Windows filesystems. The `data/` directory name itself must be lowercase (per README). Keep new data file references case-exact to avoid breaking.

## Build (frozen exe)

```
cd client
./compiler.ps1
```

Nuitka onefile build (PySide6 plugin, bundled `web/`, `web_s/`, `data/`, icons, translations, the cp39 pyd), then moves `build_console/Mini-KVM.exe` to `Mini-KVM-Client/Mini-KVM.exe`.

## Translations

`client/translate.ps1`: `pyside6-lupdate` on main.py + all `.ui` files → `trans_cn.ts` → linguist → `pyside6-lrelease` → `trans_cn.qm`. Run after touching UI strings.

## No tests / lint / CI

None exist. Manual verification only: launch with `debug`, check the video window and COM port behavior.
