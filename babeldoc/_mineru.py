import json
import requests

from pathlib import Path
from config.config import get_config
from mineru.types import MiddleJson
from mineru.render import PdfLayout, PdfRenderOptions, RenderFormat, render

config = get_config()
def parse_pdf(pdf_path: str) -> dict:
    """调用远程 MinerU API，获取解析任务结果。"""
    url = f"{config.mineru_base_url}/v1/file_parse"

    params = {
        "response_format": "json",
        "wait_timeout": 300,
        "tier": "standard",
        "ocr_mode": "ocr",
        "output_formats": ["middle_json"],
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


def download_middle_json(result: dict) -> dict:
    """根据解析结果下载 middle_json 文件。"""
    for item in result.get("files", []):
        output_files = item.get("output_files") or {}
        middle_json_info = output_files.get("middle_json")

        if middle_json_info and middle_json_info.get("file_id"):
            file_id = middle_json_info["file_id"]
            url = f"{config.mineru_base_url}/v1/files/{file_id}/content"

            response = requests.get(url, timeout=120)
            response.raise_for_status()
            return response.json()

    raise RuntimeError(
        "没有找到 middle_json 文件。"
        "请检查任务是否完成，以及 API 是否返回了 output_files.middle_json。"
    )


def render_pdf(input_file: str, task_output_dir: Path) -> dict:  

    mineru_result = parse_pdf(input_file)
    middle_json_raw = download_middle_json(mineru_result)
    middle_json = MiddleJson.from_json(
        json.dumps(middle_json_raw, ensure_ascii=False)
    )

    pdf_bytes = render(
        middle_json,
        RenderFormat.PDF,
        options=PdfRenderOptions(layout=PdfLayout.REFLOW),
    )
    dual_output_path = task_output_dir / "mineru_dual.pdf"

    with open(dual_output_path, "wb") as f:
        f.write(pdf_bytes)

    # TODO: dual_output is not processed yet
    mono_output = dual_output_path
    dual_output = dual_output_path
    return {"mono_output": mono_output, "dual_output": dual_output}
