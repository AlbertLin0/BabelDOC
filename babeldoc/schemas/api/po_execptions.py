from enum import Enum
from typing import Optional 

class PoErrorCode(Enum):
    SUCCESS = "S"
    VALIDATION_ERROR = "E_VAL_001"
    BUSINESS_ERROR = "E_BUS_002"
    SYSTEM_ERROR = "E_SYS_999"
    NOT_FOUND = "E_NOT_004"

class PoApiException(Exception):
    def __init__(self, code: PoErrorCode = PoErrorCode.SYSTEM_ERROR, message: str = "系统内部错误", job_id: Optional[str] = None):
        self.code = code
        self.message = message
        self.job_id = job_id
        super().__init__(self.message)



class PoValidationError(PoApiException):
    """字段验证失败异常"""
    def __init__(self, message: str, job_id: Optional[str] = None):
        super().__init__(code=PoErrorCode.VALIDATION_ERROR, message=message, job_id=job_id)

class PoBusinessError(PoApiException):
    """业务逻辑处理失败异常"""
    def __init__(self, message: str, job_id: Optional[str] = None):
        super().__init__(code=PoErrorCode.BUSINESS_ERROR, message=message, job_id=job_id)
