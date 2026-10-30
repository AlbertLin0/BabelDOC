import yaml
from pathlib import Path
from typing import Optional
from schemas.api.po_execptions import PoValidationError

class Config:
    _instance: Optional["Config"] = None

    def __init__(self):
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r") as f:
            self._raw = yaml.safe_load(f)

        self.lang_in = self._raw["lang_in"]
        self.lang_out = self._raw["lang_out"]
        self.model = self._raw["openai_config"]["model"]
        self.base_url = self._raw["openai_config"]["base_url"]
        self.api_key = self._raw["openai_config"]["api_key"]
        self.ignore_cache = self._raw["ignore_cache"]
        self.qps = self._raw["qps"]
        self.output_dir = Path(self._raw["output_dir"])
        self.upload_dir = Path(self._raw["upload_dir"])
        self.task_timeout = self._raw["task_timeout"]
        self.max_concurrent_translations = self._raw["max_concurrent_translations"]
        self.mineru_base_url = self._raw["mineru_base_url"]
        self.debug = self._raw["debug"]

        # PO API 
        self.ZORG = self._raw["ZORG"]
        self.callback_url = self._raw.get("callback_url")

        # 文件系统
        self.file_url = self._raw["file_url"]
        self.USERNAME = self._raw["USERNAME"]
        self.PASSWORD = self._raw["PASSWORD"]
        self.msgType_SUCCESS = self._raw["msgType_SUCCESS"]

        # timeout 
        self.task_timeout = self._raw["task_timeout"]
        self.callback_timeout = self._raw["callback_timeout"]

    @classmethod
    def get_instance(cls) -> "Config":
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

def get_config() -> Config:
    return Config.get_instance()



def verify_IFYWID(IFYWID: str) -> str:
    """从任务中提取 IFYWID"""
    if IFYWID == "FI1301":
        res = "FI1300"
    elif IFYWID == "FI1299":
        res = "FI1298"
    elif IFYWID == "FI1297":
        res = "FI1296"
    else:
        raise PoValidationError(message=f"未知 IFYYWID: {IFYWID}")
    return res

def verify_patch(SYSID: str) -> tuple[str, str]:
    """
    @return: SYSID 对应的 返回 SYSID 和 ZFILED5
    """
    """验证 SYSID 是否匹配"""
    if SYSID == "JWYX":
        return "FYMX", "YXQ"
    elif SYSID == "JWQT":
        return "FYZNT", "QTQ"
    elif SYSID == "JWS4":
        return "FYMX", "700"
    else:
        raise PoValidationError(message=f"未知 SYSID: {SYSID}")

