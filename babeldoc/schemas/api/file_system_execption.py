from enum import Enum
from typing import Optional 

class PoErrorCode(Enum):
    SUCCESS = "S"
    ERROR = "E"

class FileSystemApiException(Exception):
    def __init__(self, code: PoErrorCode = PoErrorCode.ERROR, message: str = "文件系统API异常", job_id: Optional[str] = None):
        self.code = code
        self.message = message
        self.job_id = job_id
        super().__init__(self.message)



class FileSystemUploadError(FileSystemApiException):
    """字段验证失败异常"""
    def __init__(self, message: str, job_id: Optional[str] = None):
        super().__init__(code=PoErrorCode.ERROR, message=message, job_id=job_id)

class FileSystemDownloadError(FileSystemApiException):
    """文件下载失败异常"""
    def __init__(self, message: str, job_id: Optional[str] = None):
        super().__init__(code=PoErrorCode.ERROR, message=message, job_id=job_id)
