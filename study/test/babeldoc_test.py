from pathlib import Path

assets_dir = Path(
    "/Users/alberthu/Documents/github/BabelDOC/test/outputs/"
    "f91a1f81-594d-4e20-aaef-df76214c3745/mineru_assets"
)

for path in sorted(assets_dir.rglob("*")):
    if path.is_file():
        print(path.relative_to(assets_dir), path.stat().st_size)