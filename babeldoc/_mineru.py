
import json
import requests
import fitz
import zipfile

from pathlib import Path

from babeldoc.config.config import get_config
from mineru.types import MiddleJson
from mineru.render import (
    PdfLayout,
    PdfRenderOptions,
    RenderFormat,
    render,
)
from babeldoc.translator.translator import OpenAITranslator
from babeldoc.app_devs import logger
from mineru.structures import TextSpan, PageBlock

config = get_config()

from pathlib import Path


def attach_image_paths(middle_json, assets_dir: Path):
    """
    将 MinerU ZIP 中的图片资源路径关联到 MiddleJson 的 ImageBodyBlock。

    图片命名格式：
        images/page_{page_idx}_image_{block_index}.jpg
    """
    assets_dir = assets_dir.resolve()

    attached_count = 0

    for page_idx, page in enumerate(middle_json.pages):
        for block in page.blocks:
            if getattr(block.type, "value", block.type) != "image":
                continue

            for image_body in block.content:
                if getattr(image_body.type, "value", image_body.type) != "image_body":
                    continue

                relative_path = (
                    f"images/page_{page_idx}_image_{block.index}.jpg"
                )

                image_path = assets_dir / relative_path

                if not image_path.is_file():
                    raise FileNotFoundError(
                        f"MinerU 图片资源不存在: {image_path}"
                    )

                # 将相对路径写入 MiddleJson
                image_body.image_path = relative_path

                attached_count += 1

                print(
                    f"[图片资源关联] "
                    f"page={page_idx}, "
                    f"block={block.index}, "
                    f"path={relative_path}"
                )

    print(f"共关联 {attached_count} 张图片")
def clean_llm_json_output(raw: str) -> str:
    """清理模型返回的 JSON Markdown 包装。"""
    raw = raw.strip()

    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    return raw.strip().lstrip("\ufeff")


def parse_pdf(pdf_path: str) -> dict:
    """调用远程 MinerU API，获取解析任务结果。"""

    url = f"{config.mineru_base_url}/v1/file_parse"

    params = {
        "response_format": "json",
        "wait_timeout": 300,
        "tier": "standard",
        "ocr_mode": "ocr",
        "output_formats": ["middle_json", "zip"],
    }

    with open(pdf_path, "rb") as f:
        response = requests.post(
            url,
            params=params,
            files={
                "files": (
                    Path(pdf_path).name,
                    f,
                    "application/pdf",
                )
            },
            timeout=320,
        )

    response.raise_for_status()
    return response.json()


def download_mineru_outputs(
    result: dict,
    output_dir: Path,
):
    """
    下载 MinerU 的 MiddleJson 和 ZIP 资源包。

    返回：
        middle_json_raw: MiddleJson 原始数据
        assets_dir: 解压后的资源目录
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    middle_json_raw = None
    zip_path = None

    for item in result.get("files", []):
        output_files = item.get("output_files") or {}

        # 下载 MiddleJson
        middle_info = output_files.get("middle_json")

        if middle_info and middle_info.get("file_id"):
            file_id = middle_info["file_id"]

            url = (
                f"{config.mineru_base_url}"
                f"/v1/files/{file_id}/content"
            )

            response = requests.get(url, timeout=120)
            response.raise_for_status()

            middle_json_raw = response.json()

        # 下载 ZIP
        zip_info = output_files.get("zip")

        if zip_info and zip_info.get("file_id"):
            file_id = zip_info["file_id"]

            url = (
                f"{config.mineru_base_url}"
                f"/v1/files/{file_id}/content"
            )

            response = requests.get(url, timeout=300)
            response.raise_for_status()

            zip_path = output_dir / "mineru_result.zip"
            zip_path.write_bytes(response.content)

    if middle_json_raw is None:
        raise RuntimeError("MinerU 没有返回 middle_json")

    if zip_path is None:
        raise RuntimeError("MinerU 没有返回 zip 文件")

    # 解压 ZIP
    assets_dir = output_dir / "mineru_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        assets_root = assets_dir.resolve()

        # ZIP 路径安全检查
        for info in zf.infolist():
            target = (assets_dir / info.filename).resolve()

            if not target.is_relative_to(assets_root):
                raise ValueError(
                    f"ZIP 中存在非法路径：{info.filename}"
                )

        zf.extractall(assets_dir)

    logger.info(f"MinerU 图片资源解压完成：{assets_dir}")

    return middle_json_raw, assets_dir


def create_asset_resolver(assets_dir: Path):
    assets_root = assets_dir.resolve()

    def asset_resolver(relative_path: str) -> bytes:
        print(f"[asset_resolver] 请求资源: {relative_path!r}")

        image_path = (assets_root / relative_path).resolve()

        print(f"[asset_resolver] 实际路径: {image_path}")
        print(f"[asset_resolver] 文件存在: {image_path.is_file()}")

        if not image_path.is_relative_to(assets_root):
            raise ValueError(f"非法资源路径: {relative_path}")

        if not image_path.is_file():
            raise FileNotFoundError(
                f"图片资源不存在: {relative_path}"
            )

        return image_path.read_bytes()

    return asset_resolver


def recursive_text(obj):
    """
    递归提取 InlineSpan 中的文本。
    """

    content = getattr(obj, "content", None)

    if isinstance(content, str):
        yield obj

    elif isinstance(content, list):
        for item in content:
            yield from recursive_text(item)


def collect_text_spans(middle_json: MiddleJson):
    """按照文档顺序收集所有文本 Span。"""

    spans = []

    for page in middle_json.pages:
        for block in page.blocks:
            for item in block.content:
                spans.extend(recursive_text(item))

    return spans


def translate_middle_json(
    middle_json: MiddleJson,
    translator: OpenAITranslator,
    batch_size: int = 20,
):
    """翻译 MiddleJson 中的文本。"""

    spans = collect_text_spans(middle_json)

    source_texts = [span.content for span in spans]
    translated_texts = []

    for batch_start in range(0, len(source_texts), batch_size):

        batch = source_texts[
            batch_start:batch_start + batch_size
        ]

        try:
            logger.debug(
                f"开始翻译批次：{batch_start // batch_size + 1}"
            )

            batch_prompt = json.dumps(
                batch,
                ensure_ascii=False,
            )

            response_text = translator.do_translate(batch_prompt)

            response_text = clean_llm_json_output(response_text)

            batch_result = json.loads(response_text)

            if not isinstance(batch_result, list):
                raise ValueError("模型返回结果不是 JSON 数组")

            if len(batch_result) != len(batch):
                raise ValueError(
                    f"翻译数量不匹配："
                    f"src={len(batch)}, "
                    f"dst={len(batch_result)}"
                )

            if not all(isinstance(x, str) for x in batch_result):
                raise ValueError("翻译结果中存在非字符串元素")

            translated_texts.extend(batch_result)

        except Exception as e:
            logger.exception(f"批次翻译失败：{e}")

            # 翻译失败时保留原文，防止 Span 顺序错位
            translated_texts.extend(batch)

    if len(spans) != len(translated_texts):
        raise RuntimeError("翻译结果数量与原始文本数量不一致")

    for span, translated_text in zip(spans, translated_texts):
        span.content = translated_text if translated_text else " "


def render_pages_separately(
    middle_json,
    output_path: Path,
    assets_dir: Path,
):
    # 1. 关联图片资源路径
    attach_image_paths(middle_json, assets_dir)

    # 2. 创建图片资源解析器
    asset_resolver = create_asset_resolver(assets_dir)

    merged_pdf = fitz.open()

    try:
        for index, page in enumerate(middle_json.pages):

            logger.info(f"开始渲染第 {index + 1} 页")

            # 复制 MiddleJson，只保留当前页面
            page_middle_json = middle_json.model_copy(
                deep=True,
                update={
                    "pages": [page],
                },
            )

            page_pdf_bytes = render(
                page_middle_json,
                RenderFormat.PDF,
                options=PdfRenderOptions(
                    layout=PdfLayout.REFLOW,
                    asset_resolver=asset_resolver,
                ),
            )

            # 合并当前页
            with fitz.open(
                stream=page_pdf_bytes,
                filetype="pdf",
            ) as page_pdf:

                merged_pdf.insert_pdf(page_pdf)

        merged_pdf.save(str(output_path))

    finally:
        merged_pdf.close()


def render_pdf(
    input_file: str,
    task_output_dir: Path,
    translator: OpenAITranslator,
    target_lang: str = "zh",
) -> dict:
    """
    MinerU PDF 解析 -> 文本翻译 -> PDF 渲染。
    """

    task_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 1. MinerU 解析
    mineru_result = parse_pdf(input_file)

    # 2. 下载 MiddleJson 和图片资源 ZIP
    middle_json_raw, assets_dir = download_mineru_outputs(
        mineru_result,
        task_output_dir,
    )

    middle_json = MiddleJson.from_json(
        json.dumps(
            middle_json_raw,
            ensure_ascii=False,
        )
    )

    logger.info(
        f"MinerU 解析完成，共 {len(middle_json.pages)} 页"
    )

    # 3. 翻译
    translate_middle_json(
        middle_json,
        translator,
        batch_size=20,
    )

    logger.info("文本翻译完成")

    # 4. 按源页面分别渲染
    dual_output_path = task_output_dir / "mineru_dual.pdf"

    render_pages_separately(
        middle_json,
        dual_output_path,
        assets_dir,
    )

    # TODO: 后续实现原文与译文双语对照排版
    mono_output = dual_output_path
    dual_output = dual_output_path

    return {
        "mono_output": mono_output,
        "dual_output": dual_output,
    }
