#!/usr/bin/env python3
"""Load environment variables from config.toml into the current shell.

Usage:
    # In bash/zsh:
    eval $(python config/load_env.py)

    # Or source it:
    source <(python config/load_env.py)
"""

import sys
from config_loader import load_config

def main():
    """Load and print export statements for environment variables."""
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"# Warning: {e}", file=sys.stderr)
        return 1

    env_vars = config.get('environment_variables', {})

    if not env_vars:
        print("# No environment variables found in config", file=sys.stderr)
        return 0

    # Print export statements
    for key, value in env_vars.items():
        print(f'export {key}="{value}"')

    return 0

if __name__ == "__main__":
    sys.exit(main())