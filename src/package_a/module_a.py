"""Module A with simple operations."""

import numpy as np


class Calculator:
    """A simple calculator class.
    
    Attributes:
        value (float): The current value.
    """
    
    def __init__(self, value=0):
        """Initialize the Calculator.
        
        Args:
            value (float, optional): Initial value. Defaults to 0.
        """
        self.value = value
    
    def add(self, x):
        """Add a number to the current value.
        
        Args:
            x (float): Number to add.
        
        Returns:
            float: New value after addition.
        """
        self.value += x
        return self.value
    
    def get_value(self):
        """Get the current value.
        
        Returns:
            float: Current value.
        """
        return self.value


def add_numbers(a, b):
    """Add two numbers using NumPy.
    
    Args:
        a (float): First number.
        b (float): Second number.
    
    Returns:
        float: Sum of a and b.
    
    Example:
        >>> add_numbers(2, 3)
        5.0
    """
    return np.add(a, b)
