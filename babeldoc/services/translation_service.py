
from babeldoc.schemas.api.po import (
    PoInputRequest,
    PoReturnRequest,
    PoReturnRequestDescription,
    ZDataPayload,
    PoResponseFlag,
    ZDataInput,
)
from babeldoc.schemas.api.po_execptions import PoValidationError
from babeldoc.app_devs import config
from babeldoc.config.config import verify_SYSID, random_str_generate
from babeldoc.utils.rsa import decrypt_data, encrypt_data




async def process_translation(request: PoInputRequest, ifywid: str) -> PoReturnRequestDescription:
    """翻译任务处理逻辑（占位实现，后续接入真实翻译流程）"""
    zdata = ZDataInput(**decrypt_data(request.ZDATA, request.SYSID))  # ZDataInput # 冗余操作，后续需要根据需求调整
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
            ZDATA=encrypt_data(response, request.IFYWID),
        )
    )
