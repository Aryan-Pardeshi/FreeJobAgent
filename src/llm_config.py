import os
import requests
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when there is an issue with LLM configuration or model fetching."""
    pass


def get_settings() -> dict:
    """Read LLM settings from environment variables.
    
    Returns:
        dict with keys: 'api_key', 'base_url', 'default_model'.
        Values are stripped of whitespace; base_url has trailing slashes removed.
        Empty string when missing. Never raises an exception.
    """
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    default_model = os.getenv("LLM_MODEL", "").strip()

    return {
        "api_key": api_key,
        "base_url": base_url,
        "default_model": default_model,
    }


def missing_settings(settings: dict) -> list[str]:
    """Check for missing required LLM configuration settings.
    
    Returns:
        list of missing variable names ('LLM_API_KEY', 'LLM_BASE_URL').
    """
    missing = []
    if not settings.get("api_key"):
        missing.append("LLM_API_KEY")
    if not settings.get("base_url"):
        missing.append("LLM_BASE_URL")
    return missing


def fetch_models(base_url: str, api_key: str = "", timeout: float = 10.0) -> list[str]:
    """Fetch available models from an OpenAI-compatible endpoint.
    
    Args:
        base_url: Base URL for the LLM API (e.g. https://api.openai.com/v1)
        api_key: Optional API key for authorization
        timeout: Request timeout in seconds (default 10.0)
        
    Returns:
        De-duplicated, alphabetically sorted list of model ID strings.
        
    Raises:
        ConfigError: On HTTP error, timeout, connection failure, bad JSON, or empty models.
    """
    clean_base_url = (base_url or "").strip().rstrip("/")
    if not clean_base_url:
        raise ConfigError("Base URL cannot be empty")

    url = f"{clean_base_url}/models"
    headers = {}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout:
        raise ConfigError(f"Request timed out while connecting to {clean_base_url}/models")
    except requests.RequestException as e:
        raise ConfigError(f"Failed to connect to {clean_base_url}/models: {type(e).__name__}")

    if response.status_code != 200:
        status_reason = response.reason or "Error"
        if response.status_code == 401:
            raise ConfigError("401 Unauthorized - check LLM_API_KEY")
        if response.status_code == 403:
            raise ConfigError("403 Forbidden - check LLM_API_KEY permissions")
        raise ConfigError(f"{response.status_code} {status_reason} - check LLM_BASE_URL or LLM_API_KEY")

    try:
        data = response.json()
    except Exception:
        raise ConfigError("Failed to parse JSON response from models endpoint")

    raw_items = []
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            raw_items = data["data"]
        elif "models" in data and isinstance(data["models"], list):
            raw_items = data["models"]
        else:
            raise ConfigError("Unexpected format from models endpoint (missing 'data' or 'models' list)")
    else:
        raise ConfigError("Unexpected format from models endpoint")

    model_ids = set()
    for item in raw_items:
        if isinstance(item, str):
            val = item.strip()
            if val:
                model_ids.add(val)
        elif isinstance(item, dict):
            mid = item.get("id") or item.get("name")
            if isinstance(mid, str):
                val = mid.strip()
                if val:
                    model_ids.add(val)

    if not model_ids:
        raise ConfigError("No models returned by the endpoint")

    return sorted(model_ids)
