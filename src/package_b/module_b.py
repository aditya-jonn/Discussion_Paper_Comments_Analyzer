"""Module B that uses package_a."""

import numpy as np
from package_a import Calculator, add_numbers
from config.config_loader import load_config, get_config_value

class AdvancedCalculator:
    """Advanced calculator using Calculator from package_a.

    Attributes:
        calc (Calculator): Instance of Calculator from package_a.
        config (dict): Configuration loaded from config.toml.
    """

    def __init__(self, initial_value=0):
        """Initialize the AdvancedCalculator.

        Args:
            initial_value (float, optional): Initial value. Defaults to 0.
        """
        self.calc = Calculator(initial_value)
        try:
            self.config = load_config()
        except FileNotFoundError:
            self.config = None

    def add_and_double(self, x):
        """Add a number and then double the result.

        Args:
            x (float): Number to add.

        Returns:
            float: Result after adding and doubling.
        """
        self.calc.add(x)
        return self.calc.get_value() * 2

    def get_output_path(self):
        """Get output directory from configuration.

        Returns:
            str or None: Output directory path if config exists, None otherwise.
        """
        if self.config:
            return self.config.get('paths', {}).get('output_dir')
        return None

def process_numbers(a, b):
    """Process two numbers using package_a functions.

    Args:
        a (float): First number.
        b (float): Second number.

    Returns:
        float: Sum of a and b, then multiplied by 2.

    Example:
        >>> process_numbers(3, 4)
        14.0
    """
    result = add_numbers(a, b)
    return result * 2

def main():
    """Main entry point for the process-data script."""
    print("Processing data with package_b...")

    # Example usage
    calc = AdvancedCalculator(10)
    result = calc.add_and_double(5)
    print(f"Result: {result}")

    # Use process_numbers
    result2 = process_numbers(3, 7)
    print(f"Process numbers result: {result2}")

if __name__ == "__main__":
    main()