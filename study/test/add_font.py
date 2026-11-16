import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont

FONT_ROOT = Path("/Users/alberthu/Documents/github/BabelDOC/Noto_Sans_Thai,Noto_Serif_Thai")

THAI_FONTS = {
    "NotoSansThai-Regular.ttf": FONT_ROOT / "Noto_Sans_Thai" / "static",
    "NotoSansThai-Bold.ttf": FONT_ROOT / "Noto_Sans_Thai" / "static",
    "NotoSerifThai-Regular.ttf": FONT_ROOT / "Noto_Serif_Thai" / "static",
    "NotoSerifThai-Bold.ttf": FONT_ROOT / "Noto_Serif_Thai" / "static",
}

result = {}

for font_name, font_dir in THAI_FONTS.items():
    font_path = font_dir / font_name
    if not font_path.exists():
        print(f"[WARN] 字体文件不存在: {font_path}")
        continue

    # sha3_256
    h = hashlib.sha3_256()
    with font_path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    sha3_256 = h.hexdigest()

    size = font_path.stat().st_size

    # 读取字体内部信息
    tt = TTFont(str(font_path))
    try:
        upm = tt["head"].unitsPerEm

        # 这里输出归一化值（例如 1.06 / -0.293）
        ascent = tt["hhea"].ascent / upm
        descent = tt["hhea"].descent / upm

        os2 = tt["OS/2"]
        bold = int(os2.usWeightClass >= 600)
        italic = int(bool(os2.fsSelection & 1))
        monospace = int(tt["post"].isFixedPitch != 0)

        # serif 仍按字体族名称判断（简单够用）
        name_lower = font_name.lower()
        serif = int("serif" in name_lower and "sansserif" not in name_lower)

        # 取字体内部 family name（nameID 1）
        internal_font_name = None
        for record in tt["name"].names:
            if record.nameID == 1:
                try:
                    internal_font_name = record.toUnicode()
                    break
                except Exception:
                    pass
        if internal_font_name is None:
            internal_font_name = font_name

    finally:
        tt.close()

    result[font_name] = {
        "ascent": ascent,
        "bold": bold,
        "descent": descent,
        "encoding_length": 2,
        "file_name": font_name,
        "font_name": internal_font_name,
        "italic": italic,
        "monospace": monospace,
        "serif": serif,
        "sha3_256": sha3_256,
        "size": size,
    }

print(json.dumps(result, indent=4, ensure_ascii=False))