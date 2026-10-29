from pydantic import BaseModel, Field

class OpenTextUploadResponse(BaseModel):
    """OpenText上传文件响应"""
    archId: str = Field(..., description="文件ID")
    comptype: str = Field(..., description="文件名称")
    docuId: str = Field(..., description="文件ARCID")
    fileLength: str = Field(..., description="文件大小")
    fileName: str = Field(..., description="文件名称")
    msgType: str = Field(..., description="消息是否成功(S：成功)")

