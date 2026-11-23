
import json
import sys
import subprocess
import traceback
from pathlib import Path

import fitz  # PyMuPDF

from reportlab.pdfbase import pdfmetrics

from mineru.render import render_pdf


# =========================
# 配置
# =========================

OUTPUT_DIR = Path("./thai_render_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PDF_PATH = OUTPUT_DIR / "thai_test.pdf"
PNG_PATH = OUTPUT_DIR / "thai_test.png"
REPORT_PATH = OUTPUT_DIR / "report.json"

# 泰文测试内容
THAI_TEXTS = [
    "ภาษาไทยเป็นภาษาที่มีเอกลักษณ์",
    "ประเทศไทยมีวัฒนธรรมและประวัติศาสตร์ที่ยาวนาน",
    "สวัสดี ยินดีต้อนรับ",
    "การทดสอบการแสดงผลเอกสาร PDF ด้วย MinerU",
    "ภาษาไทยมีสระและวรรณยุกต์ เช่น กิ กี กึ กื กุ กู ก่ ก้ ก๊ ก๋",
]

# 混合语言测试
MIXED_TEXT = (
    "MinerU PDF Rendering Test | "
    "ภาษาไทย | English | 中文"
)

# 泰文 Unicode 范围
THAI_START = 0x0E00
THAI_END = 0x0E7F


# =========================
# 1. 创建 MiddleJson
# =========================

def build_middle_json():
    """
    构造最小 MiddleJson。

    注意：MiddleJson 的字段结构可能随 MinerU 4.x
    小版本变化。这里通过项目实际模型构造，避免
    手工猜测字段。
    """

    from mineru.utils.enum_class import BlockType

    # 这里只输出测试文本，具体 MiddleJson schema
    # 需要根据当前安装版本的定义适配。
    raise NotImplementedError(
        "请根据当前 MinerU 版本的 MiddleJson schema "
        "实现 build_middle_json()。"
    )


# =========================
# 2. Unicode 检查
# =========================

def extract_thai_chars(text):
    return [
        c for c in text
        if THAI_START <= ord(c) <= THAI_END
    ]


def check_unicode(text):
    thai_chars = extract_thai_chars(text)

    return {
        "thai_char_count": len(thai_chars),
        "thai_codepoints": [
            f"U+{ord(c):04X}" for c in thai_chars
        ],
        "has_thai": len(thai_chars) > 0,
    }


# =========================
# 3. 字体注册检查
# =========================

def check_registered_fonts():
    fonts = pdfmetrics.getRegisteredFontNames()

    thai_candidates = [
        name for name in fonts
        if "thai" in name.lower()
        or "noto" in name.lower()
    ]

    return {
        "registered_fonts": fonts,
        "thai_font_candidates": thai_candidates,
        "has_thai_font_candidate": bool(thai_candidates),
    }


# =========================
# 4. PDF 字体检查
# =========================

def check_pdf_fonts(pdf_path):
    doc = fitz.open(pdf_path)

    all_fonts = []

    for page_index, page in enumerate(doc):
        for font in page.get_fonts(full=True):
            xref = font[0]
            basefont = font[3]
            font_type = font[2]

            all_fonts.append({
                "page": page_index + 1,
                "xref": xref,
                "name": basefont,
                "type": font_type,
            })

    return {
        "fonts": all_fonts,
        "font_count": len(all_fonts),
    }


# =========================
# 5. PDF 文本提取检查
# =========================

def check_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)

    extracted_text = "\n".join(
        page.get_text() for page in doc
    )

    thai_chars = extract_thai_chars(extracted_text)

    return {
        "extracted_text": extracted_text,
        "thai_char_count": len(thai_chars),
        "has_thai": len(thai_chars) > 0,
        "thai_codepoints": [
            f"U+{ord(c):04X}" for c in thai_chars
        ],
    }


# =========================
# 6. 页面渲染检查
# =========================

def render_page_image(pdf_path, output_path):
    doc = fitz.open(pdf_path)

    for index, page in enumerate(doc):
        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False,
        )

        image_path = output_path.with_name(
            f"thai_page_{index + 1}.png"
        )

        pix.save(image_path)

        print(f"页面截图: {image_path}")


# =========================
# 7. Poppler 检查
# =========================

def check_pdffonts(pdf_path):
    try:
        result = subprocess.run(
            ["pdffonts", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "available": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except FileNotFoundError:
        return {
            "available": False,
            "message": "未安装 pdffonts",
        }


# =========================
# 8. 主流程
# =========================

def main():

    print("=" * 60)
    print("MinerU 泰文 PDF 渲染兼容性测试")
    print("=" * 60)

    report = {}

    # 1. 测试输入 Unicode
    input_text = "\n".join(THAI_TEXTS) + "\n" + MIXED_TEXT

    report["input_unicode"] = check_unicode(input_text)

    print("\n[1] 输入文本 Unicode")
    print(json.dumps(
        report["input_unicode"],
        ensure_ascii=False,
        indent=2,
    ))

    # 2. 检查字体注册
    report["registered_fonts"] = check_registered_fonts()

    print("\n[2] ReportLab 字体注册")
    print(json.dumps(
        report["registered_fonts"],
        ensure_ascii=False,
        indent=2,
    ))

    # 3. 构造 MiddleJson
    middle_json = build_middle_json()

    # 4. 调用 MinerU render_pdf
    print("\n[3] 开始调用 render_pdf")

    pdf_bytes = render_pdf(middle_json)

    PDF_PATH.write_bytes(pdf_bytes)

    print(f"PDF 已生成: {PDF_PATH}")

    # 5. 检查 PDF 字体
    report["pdf_fonts"] = check_pdf_fonts(PDF_PATH)

    print("\n[4] PDF 字体")
    print(json.dumps(
        report["pdf_fonts"],
        ensure_ascii=False,
        indent=2,
    ))

    # 6. 检查 PDF 文本
    report["pdf_text"] = check_pdf_text(PDF_PATH)

    print("\n[5] PDF 文本提取")
    print(json.dumps(
        report["pdf_text"],
        ensure_ascii=False,
        indent=2,
    ))

    # 7. 页面截图
    render_page_image(PDF_PATH, PNG_PATH)

    # 8. pdffonts
    report["pdffonts"] = check_pdffonts(PDF_PATH)

    # 9. 生成报告
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n报告已保存:", REPORT_PATH)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
