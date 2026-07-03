"""
Skill de Generación de Datos Híbrida.
Combina la versatilidad de Faker con la inteligencia contextual de Google Gemini.
"""

from .core import DataGenerator
from .ai_engine import generate_seed_data_for_database
from .hybrid_engine import multiply_data
from .mappings import get_faker_method_for_column
from .schemas import DatabaseSchema, TableSchema, ColumnSchema, TableGenerationConfig

__all__ = [
    "DataGenerator",
    "generate_seed_data_for_database",
    "multiply_data",
    "get_faker_method_for_column",
    "DatabaseSchema",
    "TableSchema",
    "ColumnSchema",
    "TableGenerationConfig"
]

__version__ = "0.1.0"
