import os
import json
import uuid
import asyncio
import time 
import aiofiles
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from babeldoc._mineru import render_pdf
from babeldoc.format.pdf.high_level import init as babel_init
from babeldoc.format.pdf.high_level import async_translate as babeldoc_async_translate
from babeldoc.translator.translator import OpenAITranslator, set_translate_rate_limiter
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.format.pdf.translation_config import TranslationConfig, WatermarkOutputMode

import logging
logger = logging.getLogger("translation_service")
logging.basicConfig(level=logging.INFO)

from config.config import get_config
config = get_config()
#翻译器配置
TRANSLATOR_CONFIG = {
    "lang_in": config.lang_in,
    "lang_out": config.lang_out,
    "model": config.model,
    "base_url": config.base_url,
    "api_key": config.api_key,
    "ignore_cache": config.ignore_cache,
    "qps": config.qps,
}
OUTPUT_DIR = Path(config.output_dir)
UPLOAD_DIR = Path(config.upload_dir)
TASK_TIMEOUT = config.task_timeout
MAX_CONCURRENT_TRANSLATIONS = config.max_concurrent_translations
DEBUG = config.debug

app = FastAPI(title="PDF 翻译服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-PDF-Type",
        "Content-Disposition",
    ],
)


def sse_event(event_type: str, data: dict) -> str:
    """将事件封装为 SSE 格式字符串"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def to_serializable(obj):
    """递归将对象转为可 JSON 序列化的结构，跳过不可序列化的字段"""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            try:
                result[k] = to_serializable(v)
            except (TypeError, ValueError):
                continue
        return result
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    # 尝试用 str() 兜底，失败则返回 None
    try:
        return str(obj)
    except Exception:
        return None

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
        start_time = time.time()        

        #加载布局模型
        self.doc_layout_model = DocLayoutModel.load_onnx()
        end_time = time.time()
        logger.info(f"加载布局模型耗时: {end_time - start_time} 秒")

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
            start_time = time.time()
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
            
            #构建翻译配置
            cfg = TranslationConfig(
                debug=DEBUG,
                input_file=str(file_path),
                output_dir=str(task_output_dir),
                translator=translator,
                lang_in=TRANSLATOR_CONFIG["lang_in"],
                lang_out=TRANSLATOR_CONFIG["lang_out"],
                no_dual=False,   #生成双语
                no_mono=False,   #生成单语
                qps=TRANSLATOR_CONFIG["qps"],
                doc_layout_model=self.doc_layout_model,
                min_text_length=5,
                watermark_output_mode=WatermarkOutputMode.NoWatermark,
                #其他参数使用默认值
            )
            end_time = time.time()
            logger.info(f"构建翻译配置耗时: {end_time - start_time} 秒")
            
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
            logger.info(f"翻译耗时: {end_time - start_time} 秒")
            
            #验证结果文件
            print(f"单语文档路径: {mono_output}")
            print(f"双语文档路径: {dual_output}")
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




@app.post("/translate/stream")
async def translate_stream(
    file: UploadFile,
    background_tasks: BackgroundTasks,
):
    """流式翻译接口 - 通过 SSE 实时推送翻译进度事件"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        async def error_gen():
            yield sse_event("error", {"message": "仅支持PDF文件"})
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    task_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{task_id}.pdf"
    async with aiofiles.open(upload_path, "wb") as f:
        await f.write(await file.read())

    task_output_dir = OUTPUT_DIR / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)

    manager = TranslationManager.get_instance()

    translator = OpenAITranslator(
        lang_in=TRANSLATOR_CONFIG["lang_in"],
        lang_out=TRANSLATOR_CONFIG["lang_out"],
        model=TRANSLATOR_CONFIG["model"],
        base_url=TRANSLATOR_CONFIG["base_url"],
        api_key=TRANSLATOR_CONFIG["api_key"],
        ignore_cache=TRANSLATOR_CONFIG["ignore_cache"],
    )
    set_translate_rate_limiter(TRANSLATOR_CONFIG["qps"])

    cfg = TranslationConfig(
        debug=True,
        input_file=str(upload_path),
        output_dir=str(task_output_dir),
        translator=translator,
        lang_in=TRANSLATOR_CONFIG["lang_in"],
        lang_out=TRANSLATOR_CONFIG["lang_out"],
        no_dual=False,
        no_mono=False,
        qps=TRANSLATOR_CONFIG["qps"],
        doc_layout_model=manager.doc_layout_model,
        min_text_length=5,
        watermark_output_mode=WatermarkOutputMode.NoWatermark,
    )

    async def event_generator():
        mono_output = None
        dual_output = None
        try:
            async for event in babeldoc_async_translate(cfg):
                event_type = event["type"]

                # finish 事件包含 TranslateResult 对象，不可序列化，跳过转发
                # 由后续的 translation_complete 事件通知前端结果
                if event_type not in ("finish",):
                    yield sse_event(event_type, to_serializable(event))

                if event_type == "detected Scanned File":
                    logger.info("检测到扫描件，调用 MinerU 处理")
                    mineru_result = render_pdf(event["input_file"], task_output_dir)
                    mono_output = mineru_result["mono_output"]
                    dual_output = mineru_result["dual_output"]
                    break

                elif event_type == "finish":
                    result = event["translate_result"]
                    mono_output = Path(result.mono_pdf_path) if result.mono_pdf_path else None
                    dual_output = Path(result.dual_pdf_path) if result.dual_pdf_path else None
                    break

                elif event_type == "error":
                    yield sse_event("error", {"message": str(event.get("error", "未知错误"))})
                    return

            # 翻译完成，验证并存储结果
            if not mono_output or not mono_output.exists():
                yield sse_event("error", {"message": "单语文档生成失败"})
                return
            if not dual_output or not dual_output.exists():
                yield sse_event("error", {"message": "双语文档生成失败"})
                return

            manager.results[task_id] = (mono_output, dual_output)
            yield sse_event("translation_complete", {
                "task_id": task_id,
                "mono_url": f"/translate/result/{task_id}?pdf_type=mono",
                "dual_url": f"/translate/result/{task_id}?pdf_type=dual",
            })

        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            yield sse_event("error", {"message": f"翻译失败: {str(e)}"})
        finally:
            # 清理上传的临时文件
            try:
                os.unlink(upload_path)
            except:
                pass
            if task_id in manager.active_tasks:
                del manager.active_tasks[task_id]
            background_tasks.add_task(cleanup_translation_files, task_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/translate/result/{task_id}")
async def get_translation_result(task_id: str, pdf_type: str = "mono"):
    """下载翻译结果 PDF"""
    if pdf_type not in ("mono", "dual"):
        raise HTTPException(400, "pdf_type 必须为 mono 或 dual")

    manager = TranslationManager.get_instance()
    result = manager.get_result(task_id)
    if not result:
        raise HTTPException(404, "翻译结果不存在或已过期")

    mono_path, dual_path = result
    pdf_path = mono_path if pdf_type == "mono" else dual_path

    if not pdf_path or not pdf_path.exists():
        raise HTTPException(404, f"{pdf_type}语文档不存在")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{task_id}.{pdf_type}.pdf"',
        },
    )


@app.post("/translate")
async def translate_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    pdf_type: str = "mono",
) -> FileResponse:
    """
    翻译接口 - 服务间调用版本
    1. 接收上传的PDF文件
    2. 直接返回翻译后的PDF文件

    参数:
        pdf_type: 返回的PDF类型，"mono"（单语，默认）或 "dual"（双语）
    """
    if pdf_type not in ("mono", "dual"):
        raise HTTPException(400, "pdf_type 必须为 mono 或 dual")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持PDF文件")

    upload_path = UPLOAD_DIR / f"{uuid.uuid4()}.pdf"
    async with aiofiles.open(upload_path, "wb") as f:
        await f.write(await file.read())

    manager = TranslationManager.get_instance()
    task_id = None

    try:
        task_id = await manager.add_task(upload_path)
        task = manager.active_tasks[task_id]
        await asyncio.wait_for(task, timeout=TASK_TIMEOUT)

        result = manager.get_result(task_id)
        if not result:
            raise HTTPException(500, "未生成翻译结果")

        mono_path, dual_path = result
        pdf_path = mono_path if pdf_type == "mono" else dual_path

        if not pdf_path or not pdf_path.exists():
            raise HTTPException(500, f"{pdf_type}语文档生成失败")

        suffix = ".mono.pdf" if pdf_type == "mono" else ".dual.pdf"
        filename = Path(file.filename).stem + suffix
        encoded_filename = urllib.parse.quote(filename)

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            headers={
                # 使用 filename* 参数支持 UTF-8 文件名
                # 格式: filename*=UTF-8''<url_encoded_name>
                "Content-Disposition": f'inline; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}',
                "X-Request-ID": task_id,
                "X-PDF-Type": pdf_type,
            },
        )

    except asyncio.TimeoutError:
        manager.cancel_task(task_id)
        raise HTTPException(504, "翻译超时")                                 
    except Exception as e:
        manager.cancel_task(task_id)
        raise HTTPException(500, f"???翻译失败: {str(e)}")
    finally:               
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