import yaml
from pathlib import Path
from typing import Optional

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
        self.ES_OUTPUT = self._raw["ES_OUTPUT"]
        self.BSKEY = self._raw["BSKEY"]
        self.SAPKEY = self._raw["SAPKEY"]

    @classmethod
    def get_instance(cls) -> "Config":
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

def get_config() -> Config:
    return Config.get_instance()