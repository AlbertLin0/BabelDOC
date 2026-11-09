
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

def base64_to_pdf(base64_str: str, output_path: Path) -> Path:
    """
    将 base64 编码的图片转换为 PDF 文件。
    """
    image_bytes = base64.b64decode(base64_str)

    from PIL import Image
    image = Image.open(io.BytesIO(image_bytes))
    dpi = image.info.get("dpi", (72, 72))
    dpi_x, dpi_y = dpi[0], dpi[1] if len(dpi) > 1 else dpi[0]
    # 处理 RGBA 模式（如有透明通道转为 RGB） AI 推荐做法
    if image.mode == "RGBA":
        # 创建白色背景
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])  # 使用 alpha 通道作为 mask
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    img_buffer = io.BytesIO()
    image.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    doc = fitz.open()  
    img_width, img_height = image.size

    # 页面大小 = 图片大小（单位：像素 → 点，72 DPI）NOTE: DPI 应该作为超参数设置，默认值为 72 DPI
    page_width_pt = img_width / dpi_x * 72
    page_height_pt = img_height / dpi_y * 72
    page = doc.new_page(width=page_width_pt, height=page_height_pt)

    # 将图片嵌入页面（填满整页）
    page.insert_image(
        fitz.Rect(0, 0, img_width, img_height),
        stream=img_buffer.read(),
    )

    doc.save(str(output_path))
    doc.close()

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
            
            #创建翻译器
            translator = OpenAITranslator(
                lang_in=config.lang_in,
                lang_out=config.lang_out,
                model=config.model,
                base_url=config.base_url,
                api_key=config.api_key,
                ignore_cache=config.ignore_cache,
            )
            set_translate_rate_limiter(config.qps)
            
            #构建翻译配置
            cfg = TranslationConfig(
                debug=config.debug,
                input_file=str(file_path),
                output_dir=str(task_output_dir),
                translator=translator,
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
                    mineru_result = render_pdf(event["input_file"], task_output_dir)

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
            logger.error(f"翻译失败: {str(e)}")
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
        pdf_path = base64_to_pdf(zdata.PICTURE, task_output_dir / f"picture_{task_id}.pdf")

        # 直接调用 mineru 翻译 TODO: 处理翻译结果
        mineru_result = render_pdf(str(pdf_path), task_output_dir)
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
