import os
import uuid
import logging
import asyncio
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Tuple, AsyncGenerator

import aiofiles
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from babeldoc.format.pdf.high_level import init as babel_init
from babeldoc.format.pdf.high_level import async_translate as babeldoc_async_translate
from babeldoc.translator.translator import OpenAITranslator, set_translate_rate_limiter
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.format.pdf.translation_config import TranslationConfig, WatermarkOutputMode

MAX_CONCURRENT_TRANSLATIONS = 10
UPLOAD_DIR = Path("../test/uploads")
OUTPUT_DIR = Path("../test/outputs")
TASK_TIMEOUT = 3600

app = FastAPI(title="非扫描件 PDF 翻译服务（BabelDoc）")
logger = logging.getLogger("translation_service")
logging.basicConfig(level=logging.INFO)

#翻译器配置
TRANSLATOR_CONFIG = {
    "lang_in": "en",
    "lang_out": "zh",
    "model": "Qwen3-32B",
    "base_url": "http://10.16.6.191:3000/v1",
    "api_key": "sk-YmydpDkwEHMpElGtNntVubIXCOcmrsCTxBvEmQIyYD7Yxh7j",
    "ignore_cache": False,
    "qps": 4
}

class TranslationManager:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TranslationManager()
        return cls._instance

    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.results: Dict[str, Tuple[Path, Path]] = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSLATIONS)

    async def add_task(self, file_path: Path) -> str:
        task_id = str(uuid.uuid4())
    
        async with self.semaphore:
            task = asyncio.create_task(
                self._run_translation(file_path, task_id),
                name=f"translation_{task_id}"
            )   
        self.active_tasks[task_id] = task
        return task_id

    async def _run_translation(self, file_path: Path, task_id: str):
        try:
            #创建任务输出目录
            task_output_dir = OUTPUT_DIR / task_id
            task_output_dir.mkdir(parents=True, exist_ok=True)
            
            #创建翻译器
            translator = OpenAITranslator(
                lang_in=TRANSLATOR_CONFIG["lang_in"],
                lang_out=TRANSLATOR_CONFIG["lang_out"],
                model=TRANSLATOR_CONFIG["model"],
                base_url=TRANSLATOR_CONFIG["base_url"],
                api_key=TRANSLATOR_CONFIG["api_key"],
                ignore_cache=TRANSLATOR_CONFIG["ignore_cache"],
            )
            set_translate_rate_limiter(TRANSLATOR_CONFIG["qps"])
            
            #加载布局模型
            doc_layout_model = DocLayoutModel.load_onnx()
            
            #构建翻译配置
            cfg = TranslationConfig(
                input_file=str(file_path),
                output_dir=str(task_output_dir),
                translator=translator,
                lang_in=TRANSLATOR_CONFIG["lang_in"],
                lang_out=TRANSLATOR_CONFIG["lang_out"],
                no_dual=False,   #生成双语
                no_mono=False,   #生成单语
                qps=TRANSLATOR_CONFIG["qps"],
                doc_layout_model=doc_layout_model,
                min_text_length=5,
                watermark_output_mode=WatermarkOutputMode.NoWatermark,
                #其他参数使用默认值
            )

            #执行翻译
            mono_output = None
            dual_output = None
            async for event in babeldoc_async_translate(cfg):
                if event["type"] == "finish":
                    result = event["translate_result"]
                    mono_output = Path(result.mono_pdf_path) if result.mono_pdf_path else None
                    dual_output = Path(result.dual_pdf_path) if result.dual_pdf_path else None
                    break
            
            #验证结果文件
            if not mono_output or not mono_output.exists():
                raise ValueError("单语文档生成失败")
            if not dual_output or not dual_output.exists():
                raise ValueError("双语文档生成失败")
            
            self.results[task_id] = (mono_output, dual_output)
            
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            raise
        finally:
            #清理上传的临时文件
            try:
                os.unlink(file_path)
            except:
                pass
            #移除任务记录
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def get_result(self, task_id: str) -> Optional[Tuple[Path, Path]]:
        return self.results.get(task_id)

    def cancel_task(self, task_id: str | None):
        if task_id is None:
            return
        if task_id in self.active_tasks:
            self.active_tasks[task_id].cancel()
            if task_id in self.results:
                del self.results[task_id]




async def generate_zip_stream(mono_file: Path, dual_file: Path) -> AsyncGenerator[bytes, None]:
    """生成包含两个文件的ZIP流"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(mono_file, mono_file.name)
        zipf.write(dual_file, dual_file.name)
    buffer.seek(0)
    while chunk := buffer.read(4096):
        yield chunk
                    
@app.post("/translate")
async def translate_document(
    file: UploadFile,
    background_tasks: BackgroundTasks
) -> StreamingResponse:
    """
    翻译接口 - 服务间调用版本
    1. 接收上传的PDF文件
    2. 返回包含两个PDF文件的ZIP流
    """
    #验证文件类型
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持PDF文件")

    #保存上传文件
    upload_path = UPLOAD_DIR / f"{uuid.uuid4()}.pdf"
    async with aiofiles.open(upload_path, "wb") as f:
        await f.write(await file.read())

    manager = TranslationManager.get_instance()
    task_id = None

    try:
        #提交翻译任务
        task_id = await manager.add_task(upload_path)
        task = manager.active_tasks[task_id]
        
        #等待任务完成
        await asyncio.wait_for(task, timeout=TASK_TIMEOUT)
        
        #结果
        result = manager.get_result(task_id)
        if not result:
            raise HTTPException(500, "未生成翻译结果")
        
        mono_path, dual_path = result
        
        #创建ZIP流响应
        return StreamingResponse(
            generate_zip_stream(mono_path, dual_path),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={file.filename}_translated.zip",
                "X-Request-ID": task_id,
                "X-Mono-Filename": mono_path.name,
                "X-Dual-Filename": dual_path.name
            }
        )

    except asyncio.TimeoutError:
        manager.cancel_task(task_id)
        raise HTTPException(504, "翻译超时")
    except Exception as e:
        manager.cancel_task(task_id)
        raise HTTPException(500, f"翻译失败: {str(e)}")
    finally:
        #添加后台清理任务（稍后清理输出文件）
        if task_id:
            background_tasks.add_task(cleanup_translation_files, task_id)
async def cleanup_translation_files(task_id: str):
    """后台任务：清理翻译生成的文件"""
    await asyncio.sleep(300) # 5分钟后清理

    #清理结果文件
    manager = TranslationManager.get_instance()
    if task_id in manager.results:
        mono_path, dual_path = manager.results[task_id]
        try:
            if mono_path.exists():
                mono_path.unlink()
            if dual_path.exists():
                dual_path.unlink()
        except Exception:
            pass
        del manager.results[task_id]

    #清理任务目录
    task_dir = OUTPUT_DIR / task_id
    if task_dir.exists():
        try:
            task_dir.rmdir()
        except:
            pass

@app.on_event("startup")
async def app_startup():
    babel_init()
    logger.info("BabelDoc初始化完成")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)