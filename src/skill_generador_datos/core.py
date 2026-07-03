"""
generators/data_generator.py
Clase principal para la generación de datos sintéticos.
Respeta orden de llaves foráneas y constraints únicos.
Genera datos con IA automáticamente (Gemini) + multiplicación local.
Si la IA no está disponible, cae silenciosamente a generación con Faker.
"""
import itertools
import logging
import random
from typing import Dict, List, Any, Set, Optional
from collections import defaultdict, deque
from faker import Faker
from .schemas import DatabaseSchema, TableGenerationConfig
from .mappings import get_faker_method_for_column

logger = logging.getLogger(__name__)

class DataGenerator:
    def __init__(self, locale: str = "es_ES"):
        self.fake = Faker(locale)

    def generate(
        self,
        schema: DatabaseSchema,
        table_configs: List[TableGenerationConfig],
        pk_offsets: Dict[str, int] = None,
        ai_prompt: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Genera datos para las tablas solicitadas, resolviendo dependencias de FK.
        
        Flujo automático:
          1. Intenta generar semillas con IA para TODAS las tablas en una sola llamada.
          2. Para cada tabla, multiplica la semilla al target_count con hybrid_multiplier.
          3. Si la IA falla, cae silenciosamente a generación Faker clásica.
        
        Args:
            schema: Esquema completo de la BD.
            table_configs: Configuración por tabla (nombre, cantidad, seleccionada).
            pk_offsets: Offsets de PKs para evitar colisiones.
            ai_prompt: Prompt opcional del usuario para dar contexto de negocio global.
        
        Returns:
            Dict con los datos generados por tabla.
        """
        config_map = {tc.table_name: tc for tc in table_configs if tc.selected}
        tables_to_generate = list(config_map.keys())

        # 1. Topological Sort para resolver dependencias (FKs)
        ordered_tables = self._topological_sort(schema, tables_to_generate)

        # 2. Intentar generar semillas con IA para TODAS las tablas a la vez
        ai_seeds = self._try_generate_ai_seeds(schema, tables_to_generate, ai_prompt)

        # Almacenar PKs generadas para usar en FKs
        generated_pks: Dict[str, Dict[str, List[Any]]] = defaultdict(lambda: defaultdict(list))
        
        result = {}

        for table_name in ordered_tables:
            table_schema = next((t for t in schema.tables if t.name == table_name), None)
            if not table_schema:
                continue
            
            table_config = config_map[table_name]
            count = table_config.record_count
            columns = [c.name for c in table_schema.columns]

            # Si tenemos semillas de IA para esta tabla, usar flujo híbrido
            if ai_seeds and table_name in ai_seeds and ai_seeds[table_name]:
                rows = self._generate_with_ai_seeds(
                    table_schema=table_schema,
                    seed_rows=ai_seeds[table_name],
                    count=count,
                    pk_offsets=pk_offsets,
                    generated_pks=generated_pks,
                    table_name=table_name,
                )
            else:
                # Flujo Faker clásico (fallback)
                rows = self._generate_with_faker(
                    table_schema=table_schema,
                    count=count,
                    pk_offsets=pk_offsets,
                    generated_pks=generated_pks,
                    table_name=table_name,
                )

            # Determinar columnas usadas
            used_columns = columns
            if rows:
                used_columns = self._get_used_columns(table_schema)

            result[table_name] = {
                "columns": used_columns,
                "rows": rows
            }

        return result

    def _try_generate_ai_seeds(
        self,
        schema: DatabaseSchema,
        table_names: List[str],
        ai_prompt: Optional[str] = None,
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        Intenta generar semillas con Gemini para todas las tablas.
        Si falla por cualquier razón, retorna None (caer a Faker).
        """
        try:
            from .ai_engine import generate_seed_data_for_database, _get_client
            
            gemini_client = _get_client()
            if not gemini_client:
                logger.warning("[IA] ⚠️ No hay cliente Gemini configurado (GEMINI_API_KEY faltante o inválida). Usando Faker clásico.")
                return None

            logger.info(f"[IA] 🤖 Enviando solicitud a Gemini para {len(table_names)} tablas...")
            seeds = generate_seed_data_for_database(
                schema=schema,
                table_names=table_names,
                prompt=ai_prompt,
                seed_size=8,  # Pocos registros: rápido y barato
            )
            
            if seeds:
                total = sum(len(v) for v in seeds.values())
                logger.info(f"[IA] ✅ Semillas generadas exitosamente: {total} registros totales para {len(seeds)} tablas.")
            else:
                logger.warning("[IA] ⚠️ Gemini no devolvió semillas. Cayendo a Faker clásico.")
            return seeds

        except Exception as e:
            logger.error(f"[IA] ❌ FALLO generando semillas con Gemini: {e}")
            logger.warning("[IA] ⚠️ Cayendo a Faker clásico como fallback.")
            return None

    def _generate_with_ai_seeds(
        self,
        table_schema,
        seed_rows: List[Dict[str, Any]],
        count: int,
        pk_offsets: Dict[str, int],
        generated_pks: Dict[str, Dict[str, List[Any]]],
        table_name: str,
    ) -> List[List[Any]]:
        """
        Flujo híbrido: Toma semillas ya generadas por IA → multiplicador local escala al target.
        """
        from .hybrid_engine import multiply_data

        logger.info(f"[IA] Tabla '{table_name}': Multiplicando {len(seed_rows)} semillas → {count} registros...")
        
        multiplied_rows = multiply_data(
            seed_rows=seed_rows,
            target_count=count,
            table_schema=table_schema,
            fake_instance=self.fake,
        )

        # Post-procesar: Reescribir PKs autonuméricos y FKs para garantizar integridad
        columns_order = [c.name for c in table_schema.columns]
        col_idx_map = {name: idx for idx, name in enumerate(columns_order)}

        for col in table_schema.columns:
            if col.name not in col_idx_map:
                continue
            idx = col_idx_map[col.name]

            # Reescribir PKs autonuméricos secuenciales
            if col.is_primary_key and any(
                t in col.data_type.upper()
                for t in ["INT", "SERIAL", "BIGSERIAL", "SMALLSERIAL"]
            ):
                start_val = (pk_offsets.get(table_name, 0) if pk_offsets else 0) + 1
                for row_idx, row in enumerate(multiplied_rows):
                    if idx < len(row):
                        row[idx] = start_val + row_idx
                        generated_pks[table_name][col.name].append(row[idx])

            # Reescribir FKs para que apunten a PKs válidas ya generadas
            elif col.foreign_key and col.foreign_key["table"] in generated_pks:
                fk_table = col.foreign_key["table"]
                fk_col = col.foreign_key["column"]
                fk_pool = generated_pks[fk_table][fk_col]
                if fk_pool:
                    for row in multiplied_rows:
                        if idx < len(row):
                            row[idx] = random.choice(fk_pool)

            # Registrar valores de PK/unique para tablas dependientes
            elif col.is_primary_key or col.is_unique:
                for row in multiplied_rows:
                    if idx < len(row):
                        generated_pks[table_name][col.name].append(row[idx])

        # Filtrar columnas con defaults del servidor
        final_rows = self._filter_server_default_columns(table_schema, multiplied_rows, columns_order)

        return final_rows

    def _generate_with_faker(
        self,
        table_schema,
        count: int,
        pk_offsets: Dict[str, int],
        generated_pks: Dict[str, Dict[str, List[Any]]],
        table_name: str,
    ) -> List[List[Any]]:
        """
        Flujo clásico de generación usando solo Faker.
        """
        rows = []
        columns = [c.name for c in table_schema.columns]

        # Preparar generadores por columna
        generators = {}
        for col in table_schema.columns:
            if col.foreign_key and col.foreign_key["table"] in generated_pks:
                fk_table = col.foreign_key["table"]
                fk_col = col.foreign_key["column"]
                if generated_pks[fk_table][fk_col]:
                    # Generator function that picks a random existing FK value
                    generators[col.name] = lambda fk_list=generated_pks[fk_table][fk_col]: self.fake.random_element(fk_list)
                else:
                    generators[col.name] = get_faker_method_for_column(self.fake, col.name, col.data_type, table_name=table_name)
            elif col.is_primary_key and any(
                t in col.data_type.upper()
                for t in ["INT", "SERIAL", "BIGSERIAL", "SMALLSERIAL"]
            ):
                start_val = (pk_offsets.get(table_name, 0) if pk_offsets else 0) + 1
                counter = itertools.count(start_val)
                generators[col.name] = lambda c=counter: next(c)
            else:
                generators[col.name] = get_faker_method_for_column(self.fake, col.name, col.data_type, table_name=table_name)

        # Estructuras para unique constraints
        unique_sets: Dict[str, Set[Any]] = defaultdict(set)

        for i in range(count):
            row = []
            used_columns = []
            for col in table_schema.columns:
                # Omitir columnas con valor por defecto del servidor (pero NO si es PK)
                if col.default_value and any(
                    kw in col.default_value.lower()
                    for kw in ["now()", "gen_random_uuid()", "nextval(", "uuid_generate", "current_timestamp"]
                ) and not col.is_primary_key:
                    continue

                gen_func = generators[col.name]
                val = gen_func()

                # Manejar Unique constraints
                if col.is_unique or col.is_primary_key:
                    attempts = 0
                    while val in unique_sets[col.name] and attempts < 100:
                        val = gen_func()
                        attempts += 1
                    unique_sets[col.name].add(val)

                # Enforce max length si es string
                if col.max_length and isinstance(val, str):
                    val = val[:col.max_length]

                row.append(val)
                used_columns.append(col.name)

                # Guardar PKs para tablas dependientes
                if col.is_primary_key or col.is_unique:
                    generated_pks[table_name][col.name].append(val)


            rows.append(row)

        return rows

    def _get_used_columns(self, table_schema) -> List[str]:
        """Retorna la lista de columnas que realmente se generan (excluye las con defaults del servidor)."""
        used = []
        for col in table_schema.columns:
            if col.default_value and any(
                kw in col.default_value.lower()
                for kw in ["now()", "gen_random_uuid()", "nextval(", "uuid_generate", "current_timestamp"]
            ) and not col.is_primary_key:
                continue
            used.append(col.name)
        return used

    def _filter_server_default_columns(self, table_schema, rows: List[List[Any]], columns_order: List[str]) -> List[List[Any]]:
        """
        Filtra columnas con defaults del servidor de las filas multiplicadas,
        para mantener consistencia con el flujo clásico.
        """
        skip_indices = set()
        for idx, col in enumerate(table_schema.columns):
            if col.default_value and any(
                kw in col.default_value.lower()
                for kw in ["now()", "gen_random_uuid()", "nextval(", "uuid_generate", "current_timestamp"]
            ) and not col.is_primary_key:
                skip_indices.add(idx)

        if not skip_indices:
            return rows

        return [
            [val for i, val in enumerate(row) if i not in skip_indices]
            for row in rows
        ]

    def _topological_sort(self, schema: DatabaseSchema, tables: List[str]) -> List[str]:
        """
        Ordena las tablas de forma que las dependencias (FK) se generen primero.
        """
        graph = {t: [] for t in tables}
        in_degree = {t: 0 for t in tables}

        schema_tables = {t.name: t for t in schema.tables}

        for table_name in tables:
            if table_name not in schema_tables:
                continue
            for fk in schema_tables[table_name].foreign_keys:
                ref_table = fk["referenced_table"] if "referenced_table" in fk else fk.get("table")
                if ref_table in graph and ref_table != table_name:  # ignorar auto-referencias
                    graph[ref_table].append(table_name)
                    in_degree[table_name] += 1

        queue = deque([t for t in tables if in_degree[t] == 0])
        ordered = []

        while queue:
            node = queue.popleft()
            ordered.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Si hay un ciclo (ej: tables self-referencing o circular dependency), in_degree no bajará a 0
        for t in tables:
            if in_degree[t] > 0 and t not in ordered:
                ordered.append(t)

        return ordered
