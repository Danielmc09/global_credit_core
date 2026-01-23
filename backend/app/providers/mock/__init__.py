"""Mock data generators for banking providers.

This package provides country-specific mock data generators using
the Strategy Pattern with a Factory for instantiation.
"""

from .base import MockDataGenerator
from .brazil import BrazilMockDataGenerator
from .colombia import ColombiaMockDataGenerator
from .default import DefaultMockDataGenerator
from .factory import MockDataGeneratorFactory
from .italy import ItalyMockDataGenerator
from .mexico import MexicoMockDataGenerator
from .portugal import PortugalMockDataGenerator
from .spain import SpainMockDataGenerator

__all__ = [
    "MockDataGenerator",
    "MockDataGeneratorFactory",
    "SpainMockDataGenerator",
    "BrazilMockDataGenerator",
    "MexicoMockDataGenerator",
    "ItalyMockDataGenerator",
    "PortugalMockDataGenerator",
    "ColombiaMockDataGenerator",
    "DefaultMockDataGenerator",
]
