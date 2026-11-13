import json
import requests

from pathlib import Path
from babeldoc.config.config import get_config
from mineru.types import MiddleJson
from mineru.render import PdfLayout, PdfRenderOptions, RenderFormat, render
from babeldoc.translator.translator import OpenAITranslator
from babeldoc.app_devs import logger

config = get_config()

def clean_llm_json_output(raw: str) -> str:
    raw = raw.strip()
    # 移除 ```json 开头和末尾 ```
    if raw.startswith("```json"):
        raw = raw.removeprefix("```json")
    elif raw.startswith("```"):
        raw = raw.removeprefix("```")
    if raw.endswith("```"):
        raw = raw.removesuffix("```")
    raw = raw.strip().lstrip("\ufeff")
    return raw


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


def render_pdf(input_file: str, task_output_dir: Path, translator: OpenAITranslator) -> dict:  
    """
    parse_pdf 可以改为异步执行，
    但 render 函数是同步的，所以该函数需要放在线程池中执行。
    """

    mineru_result = parse_pdf(input_file)
    middle_json_raw = download_middle_json(mineru_result)
    middle_json = MiddleJson.from_json(
        json.dumps(middle_json_raw, ensure_ascii=False)
    )

    def recursive(obj) -> list: 
        # NOTE: need test
        res = []

        if isinstance(obj.content, str):
            res.append(obj.content)
        else: 
            for item in obj.content: 
                res.extend(recursive(item))
        return res
    # translate
    # 用多少个并发请求模型呢？ 
    need_translate = []
    for page in middle_json.pages:
        # 构造需要翻译的text
        for block in page.blocks:
            for i in block.content:
                need_translate.extend(recursive(i))

    translated_dict = []
    batch_size = 20
    for batch_start in range(0, len(need_translate), batch_size):
        try:
            logger.info("新一批数据")
            
            batch = need_translate[batch_start:batch_start + batch_size]
            batch_prompt = json.dumps(batch, ensure_ascii=False)
            text = translator.do_translate(batch_prompt)
            
            logger.debug(f"大模型返回内容：{text}")
            if not text.startswith("["):
                logger.warning(f"大模型返回内容非dict列表：{text}")
                text = clean_llm_json_output(text)
                logger.warning(f"修复后的text为：{text}")

            batch_result = json.loads(text)

            if not( len(batch_result) == len(batch) ):
                logger.debug(f"数组长度不匹配！src_len={len(batch)}, output_len={batch_result}")
                logger.debug(f"src: {batch}")
                logger.debug(f"output: {batch_result}")
                raise "大模型返回内容与需要翻译内容不匹配！"

            translated_dict.extend(batch_result)

        except Exception as e: 
            logger.error(f"mineru 翻译出现错误:{e}")
            
    logger.debug(f"write_back 开始")
    # 递归写回翻译结果，遍历顺序与 recursive 完全一致
    def write_back(obj, trans_iter):
        if isinstance(obj.content, str):
            tmp = next(trans_iter)
            obj.content = tmp
        else:
            for item in obj.content:
                write_back(item, trans_iter)
    try: 
        trans_iter = iter(translated_dict)
        for page in middle_json.pages:
            for block in page.blocks:
                for item in block.content:
                    write_back(item, trans_iter)
    except Exception as e: 
        logger.error(f"write_back 出现错误：{e}")



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