"""Tests for package_b."""

import pytest
from package_b import AdvancedCalculator, process_numbers


def test_advanced_calculator_init():
    """Test AdvancedCalculator initialization."""
    calc = AdvancedCalculator(5)
    assert calc.calc.get_value() == 5


def test_advanced_calculator_add_and_double():
    """Test AdvancedCalculator add_and_double method."""
    calc = AdvancedCalculator(10)
    result = calc.add_and_double(5)
    assert result == 30  # (10 + 5) * 2



def test_process_numbers():
    """Test process_numbers function."""
    result = process_numbers(3, 4)
    assert result == 14  # (3 + 4) * 2


def test_process_numbers_with_floats():
    """Test process_numbers with float inputs."""
    result = process_numbers(2.5, 2.5)
    assert result == 10.0  # (2.5 + 2.5) * 2
