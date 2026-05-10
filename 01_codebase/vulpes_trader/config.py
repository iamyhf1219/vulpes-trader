"""配置管理 — 从 .env 和 YAML 文件加载配置"""

import os
from pathlib import Path
from dotenv import load_dotenv
import yaml
from typing import Any, Dict

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


class Config:
    """配置加载器，优先 .env 再 YAML"""

    def __init__(self):
        self.mode = os.getenv("VULPES_MODE", "testnet")
        self._yaml_config: Dict[str, Any] = {}
        self._load_yaml()

    def _load_yaml(self):
        config_dir = PROJECT_ROOT / "config"
        for yaml_file in config_dir.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    self._yaml_config.update(data)

    @property
    def exchange_config(self) -> Dict[str, Any]:
        if self.mode == "testnet":
            return {
                "apiKey": os.getenv("BINANCE_TESTNET_API_KEY", ""),
                "secret": os.getenv("BINANCE_TESTNET_SECRET", ""),
                "options": {"defaultType": "swap"},
                "urls": {"api": {"public": "https://testnet.binancefuture.com/fapi/v1"}},
            }
        return {
            "apiKey": os.getenv("BINANCE_MAINNET_API_KEY", ""),
            "secret": os.getenv("BINANCE_MAINNET_SECRET", ""),
            "options": {"defaultType": "swap"},
        }

    def get(self, *keys: str, default=None):
        """安全地获取嵌套配置"""
        data = self._yaml_config
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return default
        return data if data is not None else default


config = Config()
