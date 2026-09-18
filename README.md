# Passport Photo Maker

Windows desktop passport photo editor using Tkinter, Pillow, and rembg.

## Setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Build Windows EXE

```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name PassportPhotoMaker main.py
```

The EXE will be generated in `dist/PassportPhotoMaker.exe`.

## Notes

- First AI background-removal run may download the u2net model.
- The current version uses centered cropping. Add face-aware cropping for production use.
- Confirm the required photo dimensions and background rules for each application.
