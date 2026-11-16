
from babeldoc.schemas.api.po import (
    PoInputRequest,
    PoReturnRequest,
    PoReturnRequestDescription,
    ZDataPayload,
    PoResponseFlag,
    ZDataInput,
)
from babeldoc.schemas.api.file_system import OpenTextUploadResponse
from babeldoc.schemas.api.po_execptions import PoValidationError
from babeldoc.app_devs import config
from babeldoc.config.config import verify_SYSID, random_str_generate
from babeldoc.utils.rsa import decrypt_data, encrypt_data
from babeldoc.app_devs import logger, config
import time 
from typing import Dict, Tuple
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.translator.translator import OpenAITranslator, set_translate_rate_limiter
from babeldoc.format.pdf.translation_config import TranslationConfig, WatermarkOutputMode
from babeldoc.format.pdf.high_level import async_translate as babeldoc_async_translate
from babeldoc._mineru import render_pdf
from babeldoc.file_system.opentext import file_download, file_upload
from pathlib import Path
import os 
import io
import fitz
import base64
import asyncio
from PIL import Image, ImageOps

def base64_to_pdf(
    base64_str: str,
    output_path: Path,
    default_dpi: float = 72.0,
) -> Path:
    """
    将 Base64 编码的图片转换为 PDF 文件。

    Args:
        base64_str: Base64 图片字符串，支持 Data URI 格式。
        output_path: PDF 输出路径。
        default_dpi: 图片缺少有效 DPI 信息时使用的默认 DPI。

    Returns:
        PDF 文件路径。
    """
    if not base64_str:
        raise ValueError("Base64 图片数据不能为空")

    # 1. 处理 Data URI 前缀
    if base64_str.startswith("data:") and "," in base64_str:
        base64_str = base64_str.split(",", 1)[1]

    # 2. Base64 解码
    try:
        image_bytes = base64.b64decode(base64_str, validate=True)
    except Exception as e:
        raise ValueError(f"Base64 解码失败: {e}") from e

    # 3. 加载图片
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as e:
        raise ValueError(f"图片加载失败: {e}") from e

    # 4. 处理 EXIF 方向
    image = ImageOps.exif_transpose(image)

    # 5. 获取 DPI
    dpi = image.info.get("dpi") or (default_dpi, default_dpi)

    try:
        dpi_x = float(dpi[0]) if dpi[0] else default_dpi
        dpi_y = float(dpi[1]) if len(dpi) > 1 and dpi[1] else dpi_x
    except (TypeError, ValueError, IndexError):
        dpi_x = dpi_y = default_dpi

    if dpi_x <= 0:
        dpi_x = default_dpi
    if dpi_y <= 0:
        dpi_y = default_dpi

    # 6. 统一转换为 RGB，透明区域填充白色
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")
    else:
        image = image.convert("RGB")

    img_width, img_height = image.size

    # 7. 计算 PDF 页面尺寸（PDF 单位：point）
    page_width_pt = img_width / dpi_x * 72
    page_height_pt = img_height / dpi_y * 72

    if page_width_pt <= 0 or page_height_pt <= 0:
        raise ValueError("计算得到的 PDF 页面尺寸无效")

    # 8. 将图片编码为 PNG
    img_buffer = io.BytesIO()
    image.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    # 9. 创建 PDF 并插入图片
    doc = fitz.open()

    try:
        page = doc.new_page(
            width=page_width_pt,
            height=page_height_pt,
        )

        page.insert_image(
            page.rect,
            stream=img_bytes,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc.save(str(output_path), garbage=4, deflate=True)

    finally:
        doc.close()

    logger.info(
        "图片转 PDF 成功: size=%s, dpi=(%.2f, %.2f), "
        "page_size=(%.2f, %.2f), output=%s",
        image.size,
        dpi_x,
        dpi_y,
        page_width_pt,
        page_height_pt,
        output_path,
    )

    return output_path


class TranslationManager:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TranslationManager()
        return cls._instance

    def __init__(self):
        self.results: Dict[str, Tuple[Path, Path]] = {}
        start_time = time.time()        
        #加载布局模型
        self.doc_layout_model = DocLayoutModel.load_onnx()
        end_time = time.time()
        logger.info(f"加载布局模型耗时: {end_time - start_time} 秒")
        #创建翻译器
        self.translator = OpenAITranslator(
            lang_in=config.lang_in,
            lang_out=config.lang_out,
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            ignore_cache=config.ignore_cache,
        )
        set_translate_rate_limiter(config.qps)


    async def _run_translation(self, file_path: Path, task_id: str, lang_in: str|None = None, lang_out: str|None = None):
        """
        @param file_path: 输入文件路径 工作目录+xxx+xxx.pdf
        @param task_id: 任务ID

        """
        try:
            start_time = time.time()
            #创建任务输出目录
            task_output_dir = config.output_dir / task_id
            task_output_dir.mkdir(parents=True, exist_ok=True)
            

            logger.info(f"debug mode is {config.debug}")
            #构建翻译配置
            cfg = TranslationConfig(
                debug=True,
                input_file=str(file_path),
                output_dir=str(task_output_dir),
                translator=self.translator,
                lang_in=lang_in or config.lang_in,
                lang_out=lang_out or config.lang_out,
                no_dual=False,   #生成双语
                no_mono=False,   #生成单语
                qps=config.qps,
                doc_layout_model=self.doc_layout_model,
                min_text_length=5,
                watermark_output_mode=WatermarkOutputMode.NoWatermark,
                #其他参数使用默认值
            )
            end_time = time.time()
            logger.info(f"{task_id} 构建翻译配置耗时: {end_time - start_time} 秒")
            
            start_time = time.time()    
            #执行翻译
            mono_output = None
            dual_output = None
            async for event in babeldoc_async_translate(cfg):
                if event["type"] == "detected Scanned File":
                    loop = asyncio.get_event_loop()
                    mineru_result = await loop.run_in_executor(None, render_pdf, event["input_file"], task_output_dir, self.translator)

                    mono_output = mineru_result["mono_output"]
                    dual_output = mineru_result["dual_output"]
                    break

                if event["type"] == "finish":
                    result = event["translate_result"]
                    mono_output = Path(result.mono_pdf_path) if result.mono_pdf_path else None
                    dual_output = Path(result.dual_pdf_path) if result.dual_pdf_path else None
                    break
            end_time = time.time()
            logger.info(f"{task_id} 翻译耗时: {end_time - start_time} 秒")
            
            #验证结果文件
            print(f"单语文档路径: {mono_output}")
            print(f"双语文档路径: {dual_output}")
            if not mono_output or not mono_output.exists():
                raise ValueError("单语文档生成失败")
            if not dual_output or not dual_output.exists():
                raise ValueError("双语文档生成失败")

            return mono_output, dual_output           
            # self.results[task_id] = (mono_output, dual_output)
            
        except Exception as e:
            logger.exception(e)
            logger.error(f"TRANSMANGER 翻译失败: {str(e)}")
            raise
        finally:
            #清理上传的临时文件
            try:
                os.unlink(file_path)
            except:
                pass

manager = TranslationManager.get_instance()

async def process_translation(request: PoInputRequest, ifywid: str, task_id: str) -> PoReturnRequestDescription:
    """翻译任务处理逻辑（占位实现，后续接入真实翻译流程）"""
    zdata = ZDataInput(**decrypt_data(request.ZDATA, request.SYSID))  # ZDataInput # 冗余操作，后续需要根据需求调整
    task_output_dir = config.output_dir / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)
    if zdata.PICTURE is not None:
        # 转换图片为 PDF，返回PDF路径
        logger.debug(f"图片处理")
        pdf_path = base64_to_pdf(zdata.PICTURE, task_output_dir / f"picture_{task_id}.pdf")

        # 直接调用 mineru 翻译 TODO: 处理翻译结果
        loop = asyncio.get_event_loop()
        mineru_result = await loop.run_in_executor(None, render_pdf, str(pdf_path), task_output_dir, manager.translator)
        mono_output = mineru_result["mono_output"]
        dual_output = mineru_result["dual_output"]

        if not mono_output or not mono_output.exists():
            raise ValueError("mineru单语文档生成失败")
        if not dual_output or not dual_output.exists():
            raise ValueError("mineru双语文档生成失败")

        opentext_response: OpenTextUploadResponse = await file_upload(mono_output, ArcId=zdata.FILE_ARCID or "Z1") # TODO:
        new_FILE_ID = zdata.FILE_ID
        new_FILE_NAME = opentext_response.fileName
        new_FILE_ARCID = opentext_response.archId
        new_FILE_DOCID = opentext_response.docuId
    elif zdata.FILE_ID is not None:
        # file download 
        logger.debug(f"文件处理")
        if zdata.FILE_ARCID is None or zdata.FILE_DOCID is None:
            raise ValueError("对于 file 处理 FILE_ARCID 和 FILE_DOCID 不能为空")

        # download_file_path = task_output_dir / f"file_{task_id}.pdf"
        await file_download(
            ArcId=zdata.FILE_ARCID, 
            DocId=zdata.FILE_DOCID, 
            file_path=str(task_output_dir / f"file_{task_id}.pdf")
        )
        
        mono_output, dual_output = await manager._run_translation(task_output_dir / f"file_{task_id}.pdf", task_id)

        opentext_response: OpenTextUploadResponse = await file_upload(str(mono_output), ArcId=zdata.FILE_ARCID or "Z1") # TODO:
        new_FILE_ID = zdata.FILE_ID
        new_FILE_NAME = opentext_response.fileName
        new_FILE_ARCID = opentext_response.archId
        new_FILE_DOCID = opentext_response.docuId
    else:
        raise PoValidationError(message="TEXT、PICTURE、FILE_ID 三者之一不能为空")

    response = ZDataPayload(
        JOBID=zdata.JOBID,
        CODE=PoResponseFlag.S.value,
        MESSAGE=None,
        TEXT=zdata.TEXT,
        PICTURE=zdata.PICTURE,
        FILE_ID=new_FILE_ID,
        FILE_NAME=new_FILE_NAME,
        FILE_ARCID=new_FILE_ARCID,
        FILE_DOCID=new_FILE_DOCID,
        ZEXTRA1=zdata.ZEXTRA1,
        ZEXTRA2=zdata.ZEXTRA2,
        ZEXTRA3=zdata.ZEXTRA3,
        ZEXTRA4=zdata.ZEXTRA4,
        ZEXTRA5=zdata.ZEXTRA5,
    )
    _SYSID, _ZFILED5 = verify_SYSID(request.SYSID)
    return PoReturnRequestDescription(
        IS_INPUT=PoReturnRequest(
            SYSID=_SYSID,
            IFYWID=ifywid,
            BSKEY=f"{ifywid}_{random_str_generate()}",
            SAPKEY=f"{ifywid}_{random_str_generate()}",
            ZORG=None,
            ZFILED1=request.ZFILED1,
            ZFILED2=request.ZFILED2,
            ZFILED3=request.ZFILED3,
            ZFILED4=request.ZFILED4,
            ZFILED5=_ZFILED5,
            ZDATA=encrypt_data(response, request.SYSID),
        )
    )
