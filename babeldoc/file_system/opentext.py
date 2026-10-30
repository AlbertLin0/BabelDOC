import httpx 
from babeldoc.config.config import get_config
from babeldoc.schemas.api.file_system_execption import FileSystemUploadError, FileSystemDownloadError
from babeldoc.schemas.api.file_system import OpenTextUploadResponse
import logging
logger = logging.getLogger(__name__)

config = get_config()

async def file_upload(file_path: str, ArcId: str) -> OpenTextUploadResponse:
    """从工作区中上传文件到OpenText"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.file_url}/uploadFile/UploadServlet?ArcId={ArcId}",
            files={"file": open(file_path, "rb")},
            auth=(config.USERNAME, config.PASSWORD),
        )
        response.raise_for_status()
        if response.status_code == 200 and response.json()["msgType"] == config.msgType_SUCCESS:
            return OpenTextUploadResponse(**response.json())
        else:
            logger.error(f"文件上传失败，状态码：{response.status_code}，响应内容：{response.json()}")
            raise FileSystemUploadError(f"文件上传失败，状态码：{response.status_code}")


async def file_download(ArcId: str, DocId: str, file_path: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{config.file_url}/uploadFile/ShowFile?ArcId={ArcId}&DocId={DocId}",
            auth=(config.USERNAME, config.PASSWORD),
        )
        response.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(response.content)
