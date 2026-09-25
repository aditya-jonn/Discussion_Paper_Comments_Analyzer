"""Tests for package_a."""

import numpy as np
from package_a import Calculator, add_numbers


def test_calculator_init():
    """Test Calculator initialization."""
    calc = Calculator(5)
    assert calc.get_value() == 5


def test_calculator_add():
    """Test Calculator add method."""
    calc = Calculator(10)
    result = calc.add(5)
    assert result == 15
    assert calc.get_value() == 15


def test_calculator_default_value():
    """Test Calculator with default value."""
    calc = Calculator()
    assert calc.get_value() == 0


def test_add_numbers():
    """Test add_numbers function."""
    result = add_numbers(3, 7)
    assert result == 10


def test_add_numbers_with_floats():
    """Test add_numbers with float inputs."""
    result = add_numbers(2.5, 3.5)
    assert result == 6.0
