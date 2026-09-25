"""Centralized configuration loader for InSilicoSuite.

This module provides a centralized way to load configuration from config.toml
and should be used by all packages instead of having their own load_config functions.
"""

import os
from pathlib import Path
from typing import Dict, Any

if __name__ == "__main__":
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If config file is not found.
    """
    if config_path is None:
        # Try to find config in standard locations
        # First, try relative to this file (config directory)
        config_path = Path(__file__).parent / "config.toml"

        # If not found, try relative to project root
        if not config_path.exists():
            config_path = Path(__file__).resolve().parents[1] / "config" / "config.toml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Please ensure config.toml exists in the config directory."
        )

    with open(config_path, 'rb') as f:
        return tomllib.load(f)

def get_config_value(key: str, config_path: str = None, default: Any = None) -> Any:
    """Get a specific configuration value.

    Args:
        key: Configuration key (e.g., 'paths.data_dir' or 'env.PYTHON_VERSION')
        config_path: Path to config file. If None, uses default location.
        default: Default value to return if key is not found.

    Returns:
        The configuration value or default if not found.
    """
    try:
        config = load_config(config_path)
        keys = key.split('.')
        value = config
        for k in keys:
            value = value.get(k, default)
            if value == default:
                break
        return value if value != default else default
    except (FileNotFoundError, KeyError):
        return default