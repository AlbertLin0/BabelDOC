from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # 仅用于类型标注，避免循环导入
    from schemas.api.po import PoInputRequestDescription

class PoErrorCode(Enum):
    SUCCESS = "S"
    VALIDATION_ERROR = "E_VAL_001"
    BUSINESS_ERROR = "E_BUS_002"
    SYSTEM_ERROR = "E_SYS_999"
    NOT_FOUND = "E_NOT_004"

class PoApiException(Exception):
    def __init__(
        self,
        code: PoErrorCode = PoErrorCode.SYSTEM_ERROR,
        message: str = "系统内部错误",
        job_id: Optional[str] = None,
        # 可选：携带原始请求对象，供异常处理器组装响应时取用 BSKEY/SAPKEY 等字段
        request: Optional["PoInputRequestDescription"] = None,
    ):
        self.code = code
        self.message = message
        self.job_id = job_id
        self.request = request
        super().__init__(self.message)



class PoValidationError(PoApiException):
    """字段验证失败异常"""
    def __init__(self, message: str, job_id: Optional[str] = None, request: Optional["PoInputRequestDescription"] = None):
        super().__init__(code=PoErrorCode.VALIDATION_ERROR, message=message, job_id=job_id, request=request)

class PoBusinessError(PoApiException):
    """业务逻辑处理失败异常"""
    def __init__(self, message: str, job_id: Optional[str] = None, request: Optional["PoInputRequestDescription"] = None):
        super().__init__(code=PoErrorCode.BUSINESS_ERROR, message=message, job_id=job_id, request=request)
