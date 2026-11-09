import httpx
from urllib.parse import urlparse
from babeldoc.config.config import get_config
from babeldoc.schemas.api.file_system_execption import FileSystemUploadError, FileSystemDownloadError
from babeldoc.schemas.api.file_system import OpenTextUploadResponse
import logging
logger = logging.getLogger(__name__)

config = get_config()

async def file_upload(file_path: str, ArcId: str) -> OpenTextUploadResponse:
    """从工作区中上传文件到OpenText"""
    async with httpx.AsyncClient() as client:
        headers = {
            "USERNAME": config.USERNAME,
            "PASSWORD": config.PASSWORD
        }
        response = await client.post(
            f"{config.file_url}/uploadFile/UploadServlet?ArcId={ArcId}",
            files={"file": open(file_path, "rb")},
            headers=headers
        )
        response.raise_for_status()
        tmp = response.json()[0]
        if response.status_code == 200 and tmp["msgType"] == config.msgType_SUCCESS:
            return OpenTextUploadResponse(**tmp)
        else:
            logger.error(f"文件上传失败，状态码：{response.status_code}，响应内容：{response.json()}")
            raise FileSystemUploadError(f"文件上传失败，状态码：{response.status_code}")
            

async def file_download(ArcId: str, DocId: str, file_path: str) -> None:
    # 从 file_url 提取外网 host（如 10.0.0.111:8080）
    external_host = urlparse(config.file_url).netloc

    async with httpx.AsyncClient(follow_redirects=False) as client:
        response = await client.get(
            f"{config.file_url}/uploadFile/ShowFile?ArcId={ArcId}&DocId={DocId}",
        )

        # 服务端返回 302 重定向，Location 中包含内网 IP，需要替换为外网 host
        if response.status_code == 302:
            location = response.headers.get("Location")
            if not location:
                raise FileSystemDownloadError("302 响应缺少 Location 头")

            # 将 Location 中的内网 host 替换为外网 host
            parsed = urlparse(location)
            redirect_url = location.replace(parsed.netloc, external_host, 1)

            logger.info(f"重定向下载地址从 {parsed.netloc} 替换为 {external_host}")

            # 请求替换后的重定向地址，获取 PDF 流
            response = await client.get(redirect_url)

        response.raise_for_status()

        if not file_path.endswith(".pdf"):
            raise FileSystemDownloadError("文件路径必须以 .pdf 结尾")

        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
