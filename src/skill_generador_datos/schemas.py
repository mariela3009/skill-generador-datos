from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict

class ColumnSchema(BaseModel):
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default_value: Optional[str] = None
    foreign_key: Optional[Dict[str, str]] = None  # {"table": "...", "column": "..."}
    max_length: Optional[int] = None

class TableSchema(BaseModel):
    name: str
    columns: List[ColumnSchema]
    primary_keys: List[str] = []
    foreign_keys: List[Dict[str, Any]] = []

class DatabaseSchema(BaseModel):
    motor: str
    database_name: str
    tables: List[TableSchema]

class TableGenerationConfig(BaseModel):
    table_name: str
    record_count: int = Field(..., ge=1, le=100000)
    selected: bool = True
