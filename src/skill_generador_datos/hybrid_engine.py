"""
generators/hybrid_multiplier.py
Multiplicador híbrido que escala una pequeña "semilla" de datos (ej. 50 registros generados por IA)
hasta alcanzar miles de registros (ej. 10000) en milisegundos.
"""
import random
from typing import List, Dict, Any
from faker import Faker
from .schemas import TableSchema
from .mappings import NAME_MAPPINGS

def multiply_data(seed_rows: List[Dict[str, Any]], target_count: int, table_schema: TableSchema, fake_instance: Faker) -> List[List[Any]]:
    """
    Toma una lista de diccionarios (semilla generada por IA), 
    el número objetivo de registros, y devuelve una lista de listas (filas) multiplicadas.
    """
    if not seed_rows:
        return []

    # Extraer pools de valores por columna desde la semilla
    pools: Dict[str, List[Any]] = {col.name: [] for col in table_schema.columns}
    for row in seed_rows:
        for col_name, val in row.items():
            if col_name in pools:
                pools[col_name].append(val)

    # Identificar qué columnas delegar 100% a Faker para máxima unicidad (ej. IDs, correos, uuids)
    # y cuáles escalar usando la semilla de la IA.
    faker_overrides = {}
    
    # Preprocesar tipos de columnas
    col_strategies = {}
    import re
    
    for col in table_schema.columns:
        # 1. Si es PK o Unique, Faker/Sequences debe encargarse en el DataGenerator principal, 
        # pero para que el multiplicador no rompa la estructura, marcamos como "skip" o dejamos 
        # que el generator original asigne la PK después.
        # Aquí asignaremos valores base que el data_generator.py reescribirá si es PK.
        
        is_faker_friendly = False
        # Chequear si es un mapping explícito como email, uuid, ip
        for pattern, method_name in NAME_MAPPINGS:
            if re.search(pattern, col.name):
                # Para emails, uuids, passwords, preferimos Faker para evitar duplicados masivos
                if method_name in ["email", "uuid4", "password", "iban", "credit_card_number"]:
                    is_faker_friendly = True
                    faker_overrides[col.name] = getattr(fake_instance, method_name)
                break
                
        if is_faker_friendly:
            col_strategies[col.name] = "faker"
        elif any(t in col.data_type.upper() for t in ["INT", "SERIAL", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC"]):
            col_strategies[col.name] = "number_jitter"
        else:
            col_strategies[col.name] = "seed_permutation"

    # Generar filas multiplicadas
    multiplied_rows = []
    columns_order = [col.name for col in table_schema.columns]

    for i in range(target_count):
        if i < len(seed_rows):
            # Usar la fila exacta de la semilla para los primeros registros
            row = []
            for col_name in columns_order:
                row.append(seed_rows[i].get(col_name))
            multiplied_rows.append(row)
        else:
            # Generar una nueva fila mutando/permutando
            row = []
            for col in table_schema.columns:
                col_name = col.name
                strategy = col_strategies[col_name]
                pool = pools[col_name]
                
                if strategy == "faker" and col_name in faker_overrides:
                    # Usar Faker directamente (garantiza variedad en emails, etc)
                    row.append(faker_overrides[col_name]())
                elif strategy == "number_jitter" and pool:
                    # Variar un poco el número de la semilla
                    base_val = random.choice(pool)
                    if base_val is not None:
                        try:
                            num = float(base_val)
                            # Jitter de +/- 15%
                            jitter = num * random.uniform(-0.15, 0.15)
                            new_val = num + jitter
                            if "INT" in col.data_type.upper() or "SERIAL" in col.data_type.upper():
                                row.append(int(new_val))
                            else:
                                row.append(round(new_val, 2))
                        except (ValueError, TypeError):
                            row.append(base_val)
                    else:
                        row.append(None)
                elif strategy == "seed_permutation" and pool:
                    # Mezclar textos. Si hay múltiples palabras, a veces combinamos.
                    val = random.choice(pool)
                    # Ocasionalmente (20% de las veces) hacer un mix simple si es string largo
                    if val and isinstance(val, str) and len(val.split()) > 1 and random.random() < 0.2:
                        other_val = random.choice(pool)
                        if other_val and isinstance(other_val, str) and len(other_val.split()) > 1:
                            parts1 = val.split()
                            parts2 = other_val.split()
                            val = f"{parts1[0]} {parts2[-1]}"
                    row.append(val)
                else:
                    # Fallback (ej. el pool está vacío)
                    row.append(None)
                    
            multiplied_rows.append(row)
            
    return multiplied_rows
