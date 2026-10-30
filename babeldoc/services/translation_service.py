import random
import string
from schemas.api.po import (
    PoInputRequest,
    PoReturnRequest,
    PoReturnRequestDescription,
    ZDataPayload,
    PoResponseFlag,
)
from schemas.api.po_execptions import PoValidationError
from app_devs import config
from config.config import verify_patch

def random_str_generate(length: int = 10) -> str:
    """生成随机字符串"""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))



async def process_translation(request: PoInputRequest) -> PoReturnRequestDescription:
    """翻译任务处理逻辑（占位实现，后续接入真实翻译流程）"""
    zdata = request.ZDATA  # ZDataInput
    if zdata.PICTURE is not None:
        new_FILE_ID = "FI23456"
        new_FILE_NAME = f"{zdata.FILE_NAME}_translated.png"
        new_FILE_ARCID = zdata.FILE_ARCID
        new_FILE_DOCID = zdata.FILE_DOCID
    elif zdata.FILE_ID is not None:
        new_FILE_ID = "FI23456"
        new_FILE_NAME = f"{zdata.FILE_NAME}_translated.png"
        new_FILE_ARCID = zdata.FILE_ARCID
        new_FILE_DOCID = zdata.FILE_DOCID
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
    _SYSID, _ZFILED5 = verify_patch(request.SYSID)
    return PoReturnRequestDescription(
        IS_INPUT=PoReturnRequest(
            SYSID=_SYSID,
            IFYWID=request.IFYWID,
            BSKEY=f"{request.IFYWID}_{random_str_generate()}",
            SAPKEY=f"{request.IFYWID}_{random_str_generate()}",
            ZORG=None,
            ZFILED1=request.ZFILED1,
            ZFILED2=request.ZFILED2,
            ZFILED3=request.ZFILED3,
            ZFILED4=request.ZFILED4,
            ZFILED5=_ZFILED5,
            ZDATA=response,
        )
    )
