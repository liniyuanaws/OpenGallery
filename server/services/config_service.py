import os
import traceback
import toml

# Default providers configuration - should match frontend constants.ts
DEFAULT_PROVIDERS_CONFIG = {
    "anthropic": {
        "models": {
            "claude-3-7-sonnet-latest": {"type": "text"}
        },
        "url": "https://api.anthropic.com/v1/",
        "api_key": "",
        "max_tokens": 8192
    },
    "openai": {
        "models": {
            "gpt-4o": {"type": "text"},
            "gpt-4o-mini": {"type": "text"},
            "gpt-image-1": {"type": "image"}
        },
        "url": "https://api.openai.com/v1/",
        "api_key": "",
        "max_tokens": 8192
    },
    "comfyui": {
        "models": {
            "flux-kontext": {"type": "image"},
            "flux-t2i": {"type": "image"}
        },
        "url": "http://comfyui-alb-905118004.us-west-2.elb.amazonaws.com:8080",
        "api_key": ""
    },
    "bedrock": {
        "models": {
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0": {"type": "text"}
        },
        "url": "",
        "api_key": "",
        "max_tokens": 8192,
        "region": "us-west-2"
    }
}

# Database configuration
DEFAULT_DATABASE_CONFIG = {
    "database": {
        "type": "sqlite",  # "sqlite" or "dynamodb"
        "sqlite": {
            "path": None  # Will use default path if None
        },
        "dynamodb": {
            "region": "us-west-2"
        }
    }
}

USER_DATA_DIR = os.getenv("USER_DATA_DIR", os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "user_data"))
FILES_DIR = os.path.join(USER_DATA_DIR, "files")


class ConfigService:
    def __init__(self):
        self.app_config = DEFAULT_PROVIDERS_CONFIG
        self.db_config = DEFAULT_DATABASE_CONFIG
        self.root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(__file__)))
        self.config_file = os.getenv(
            "CONFIG_PATH", os.path.join(USER_DATA_DIR, "config.toml"))
        # 初次加载配置，赋值给 app_config
        self._load_config_from_file()

    def _load_config_from_file(self):
        try:
            with open(self.config_file, 'r') as f:
                config = toml.load(f)

            # Merge provider config with defaults
            merged_config = DEFAULT_PROVIDERS_CONFIG.copy()
            for provider, provider_config in config.items():
                if provider == 'database':
                    # Handle database config separately
                    continue
                elif provider in merged_config:
                    # Merge provider config with defaults
                    merged_config[provider] = {**merged_config[provider], **provider_config}
                    # Merge models specifically
                    if 'models' in provider_config and 'models' in merged_config[provider]:
                        merged_config[provider]['models'] = {
                            **merged_config[provider]['models'],
                            **provider_config['models']
                        }
                else:
                    # Add new provider not in defaults
                    merged_config[provider] = provider_config
            self.app_config = merged_config

            # Handle database config
            if 'database' in config:
                self.db_config = {**DEFAULT_DATABASE_CONFIG, **config}
            else:
                self.db_config = DEFAULT_DATABASE_CONFIG.copy()

        except Exception as e:
            print(f"Config file not found or invalid, using defaults: {e}")
            # Use default config if file doesn't exist or is invalid
            self.app_config = DEFAULT_PROVIDERS_CONFIG.copy()
            self.db_config = DEFAULT_DATABASE_CONFIG.copy()

    def get_config(self):
        # 直接返回内存中的配置
        return self.app_config

    def get_database_config(self):
        """Get database configuration"""
        return self.db_config.get('database', DEFAULT_DATABASE_CONFIG['database'])

    async def exists_config(self):
        """Check if config file exists"""
        return os.path.exists(self.config_file)

    async def update_config(self, data):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                toml.dump(data, f)
            self.app_config = data

            return {"status": "success", "message": "Configuration updated successfully"}
        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "message": str(e)}


config_service = ConfigService()
