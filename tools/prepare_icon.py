"""Convert the application logo to a Windows icon at standard display sizes."""

from pathlib import Path

from PIL import Image


def main():
    assets = Path(__file__).resolve().parents[1] / "src" / "ui" / "assets"
    target = assets / "app.ico"
    with Image.open(assets / "logo.png") as image:
        image.convert("RGBA").save(
            target,
            format="ICO",
            sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
        )
    print(f"Prepared {target.name}")


if __name__ == "__main__":
    main()
