from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

class PoResponseFlag(Enum):
    """处理消息标识(S：成功，E：失败)"""
    S = "S"
    E = "E"

# ZDATA 内部的业务数据结构
class ZDataPayload(BaseModel):
    JOBID: str = Field(..., description="任务ID UUID")
    CODE: Literal["S", "E"] = Field(..., description="处理消息标识(S：成功，E：失败)")
    MESSAGE: Optional[str] = Field(None, description="处理消息文本")
    TEXT: Optional[str] = Field(None, description="文本，与FILE字段互斥")
    PICTURE: Optional[str] = Field(None, description="图片，与TEXT字段互斥")
    FILE_ID: Optional[str] = Field(None, description="原文件ID")
    FILE_NAME: Optional[str] = Field(None, description="文件名称")
    FILE_ARCID: Optional[str] = Field(None, description="处理后文件ARCID")
    FILE_DOCID: Optional[str] = Field(None, description="处理后文件DOCID")
    ZEXTRA1: Optional[str] = Field(None, description="备用字段1")
    ZEXTRA2: Optional[str] = Field(None, description="备用字段2")
    ZEXTRA3: Optional[str] = Field(None, description="备用字段3")
    ZEXTRA4: Optional[str] = Field(None, description="备用字段4")
    ZEXTRA5: Optional[str] = Field(None, description="备用字段5")


# 最外层的 IS_INPUT 结构
class PoInputRequest(BaseModel):
    IS_INPUT: str = Field(..., description="固定值：IS_INPUT") # 字段类型？
    SYSID: str = Field(..., description="外围系统，固定值：JWQT")
    IFYWID: str = Field(..., description="接口业务ID")
    BSKEY: str = Field(..., description="外围系统数据唯一标识")
    SAPKEY: Optional[str] = Field(None, description="SAP数据唯一标识")
    ZORG: Optional[str] = Field(None, description="组织机构代码")
    ZFILED1: Optional[str] = Field(None, description="预留字段")
    ZFILED2: Optional[str] = Field(None, description="预留字段")
    ZFILED3: Optional[str] = Field(None, description="预留字段")
    ZFILED4: Optional[str] = Field(None, description="预留字段")
    ZFILED5: str = Field(..., description="系统服务器") # 备注说是必填
    ZDATA: ZDataPayload = Field(..., description="业务数据JSON串") 

    class Config:
        # 禁止额外字段，防止对方多传了字段导致报错
        extra = "forbid" 

class ZDataResponse(BaseModel):
    JOBID: str = Field(..., description="任务ID UUID")
    CODE: str = Field(..., description="错误码")
    MESSAGE: Optional[str] = Field(None, description="处理消息文本")

class PoOutputResponse(BaseModel):
    ES_OUTPUT: str = Field(..., description="固定值：ES_OUTPUT") # 字段类型？
    BSKEY: str = Field(..., description="外围系统数据唯一标识")
    SAPKEY: str = Field(..., description="SAP数据唯一标识")
    ZTYPE: Literal["S", "E"] = Field(..., description="处理消息标识(S：成功，E：失败)")
    ZMESSAGE: str = Field(..., description="处理消息文本")
    ZDATA: ZDataResponse = Field(..., description="返回业务数据JSON串")

