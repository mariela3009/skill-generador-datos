"""
generators/ai_generator.py
Módulo para interactuar con Google Gemini y generar la 'semilla' de datos.
Genera datos para TODA la base de datos en una sola llamada (no por tabla).
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from .schemas import DatabaseSchema, TableSchema

logger = logging.getLogger(__name__)

# Cargar .env para asegurar que GEMINI_API_KEY esté disponible
load_dotenv()

# Lazy client initialization
client = None

def _get_client():
    """Inicializa el cliente de Gemini de forma lazy."""
    global client
    if client is not None:
        return client
    
    try:
        from google import genai
        
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("No se encontró GEMINI_API_KEY ni GOOGLE_API_KEY en las variables de entorno.")
            return None
        
        client = genai.Client(api_key=api_key)
        logger.info("Cliente de Gemini inicializado correctamente.")
        return client
    except ImportError:
        logger.warning("google-genai no está instalado. pip install google-genai")
        return None
    except Exception as e:
        logger.warning(f"Error inicializando cliente Gemini: {e}")
        return None


def generate_seed_data_for_database(
    schema: DatabaseSchema,
    table_names: List[str],
    prompt: Optional[str] = None,
    seed_size: int = 8,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Genera datos semilla para TODAS las tablas seleccionadas en una sola llamada a Gemini.
    
    Args:
        schema: Esquema completo de la base de datos.
        table_names: Lista de nombres de tablas seleccionadas.
        prompt: Prompt opcional del usuario para dar contexto de negocio.
        seed_size: Cantidad de registros semilla por tabla (default: 8).
    
    Returns:
        Dict con { "tabla1": [{...}, ...], "tabla2": [{...}, ...] }
    """
    gemini_client = _get_client()
    if not gemini_client:
        raise ValueError("El cliente de Gemini no está configurado correctamente. Revisa GEMINI_API_KEY en .env.")

    from google.genai import types

    # Filtrar solo las tablas seleccionadas
    selected_tables = [t for t in schema.tables if t.name in table_names]
    if not selected_tables:
        raise ValueError("No se encontraron tablas seleccionadas en el esquema.")

    # Construir descripción de TODAS las tablas
    tables_description = []
    for table in selected_tables:
        columns_info = []
        for col in table.columns:
            info = f"    - {col.name}: {col.data_type}"
            constraints = []
            if not col.is_nullable:
                constraints.append("NOT NULL")
            if col.is_primary_key:
                constraints.append("PRIMARY KEY")
            if col.is_unique:
                constraints.append("UNIQUE")
            if col.foreign_key:
                constraints.append(f"FOREIGN KEY -> {col.foreign_key['table']}.{col.foreign_key['column']}")
            if col.max_length:
                constraints.append(f"MAX LENGTH = {col.max_length}")
            if constraints:
                info += f" ({', '.join(constraints)})"
            columns_info.append(info)

        table_block = f"  TABLA: {table.name}\n" + "\n".join(columns_info)
        tables_description.append(table_block)

    full_schema_str = "\n\n".join(tables_description)

    # Construir el prompt del sistema
    system_instruction = (
        f"Actúa como un generador experto de datos de prueba (mock data) de alta calidad y realismo.\n"
        f"Tu tarea es generar EXACTAMENTE {seed_size} registros para CADA una de las tablas de la siguiente base de datos.\n\n"
        f"**BASE DE DATOS: {schema.database_name} (Motor: {schema.motor})**\n\n"
        f"**ESQUEMA COMPLETO:**\n"
        f"{full_schema_str}\n\n"
        f"**REGLAS CRÍTICAS:**\n"
        f"1. Devuelve UN SOLO objeto JSON válido donde cada clave es el nombre EXACTO de una tabla y su valor es un arreglo de {seed_size} objetos.\n"
        f"2. Formato exacto: {{ \"tabla1\": [{{...}}, ...], \"tabla2\": [{{...}}, ...] }}\n"
        f"3. Respeta estrictamente los tipos de datos (números SIN comillas, booleanos como true/false).\n"
        f"4. **ANALIZA LOS NOMBRES de las tablas y columnas para inferir QUÉ tipo de datos deberían contener:**\n"
        f"   - Si la tabla se llama 'producto' y hay una columna 'nombre', genera NOMBRES DE PRODUCTOS reales y atractivos (ej: 'Laptop HP Pavilion', 'Auriculares Sony WH-1000XM5', 'Cámara Canon EOS R5').\n"
        f"   - Si hay una columna 'categoria', genera CATEGORÍAS reales (ej: 'Electrónica', 'Hogar', 'Deportes').\n"
        f"   - Si hay una columna 'email', genera emails realistas.\n"
        f"   - Si hay una columna 'role' o 'rol', genera roles reales del dominio (ej: 'admin', 'editor', 'viewer').\n"
        f"   - SIEMPRE infiere el significado del nombre de la columna y genera datos apropiados para ese contexto.\n"
        f"5. NO uses textos genéricos tipo 'Lorem Ipsum', 'Test', 'Example', ni texto largo sin sentido. Datos CORTOS, CONCRETOS y REALES.\n"
        f"6. Los datos entre tablas deben ser COHERENTES: si una tabla tiene FK a otra, los valores deben coincidir con los PKs de la tabla referenciada.\n"
        f"7. Para PKs de tipo entero (INT, SERIAL, etc.), usa valores SIMPLES consecutivos: 1, 2, 3, 4...\n"
        f"8. Para PKs de tipo UUID o texto, usa valores CORTOS y simples, no UUIDs largos innecesarios. Si el tipo de dato requiere UUID, usa UUIDs; para columnas tipo VARCHAR (incluyendo PKs), usa identificadores cortos de máximo 8 caracteres (ej: 'ID1', 'PROD01').\n"
        f"9. NO incluyas markdown (como ```json) en tu respuesta, SOLO el JSON puro.\n"
        f"10. Los datos deben contar una historia coherente — como si fueran de un sistema en producción real.\n"
    )

    if prompt:
        system_instruction += f"\n**CONTEXTO ESPECÍFICO DEL USUARIO:**\n{prompt}\n"
    else:
        system_instruction += (
            "\n**INSTRUCCIONES DE CONTEXTO:**\n"
            "Infiere el dominio de negocio basándote en los nombres de las tablas y columnas. "
            "Genera datos lógicos, coherentes y realistas para ese dominio. "
            "Los nombres de columnas son tu guía principal para saber qué tipo de dato generar.\n"
        )

    try:
        logger.info(f"[IA] Solicitando {seed_size} registros semilla para {len(selected_tables)} tablas a Gemini...")
        
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents="Genera el objeto JSON con los datos realistas para todas las tablas. Recuerda: analiza el nombre de cada columna para generar datos apropiados.",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
        )

        # Limpiar respuesta
        result_text = response.text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        # Parsear JSON
        data = json.loads(result_text)
        if not isinstance(data, dict):
            raise ValueError("Gemini no devolvió un objeto JSON con las tablas.")

        # Validar que cada tabla tenga una lista
        result = {}
        for table_name in table_names:
            if table_name in data and isinstance(data[table_name], list):
                result[table_name] = data[table_name]
                logger.info(f"[IA] Tabla '{table_name}': {len(data[table_name])} registros semilla recibidos.")
            else:
                logger.warning(f"[IA] Tabla '{table_name}': no se encontraron datos en la respuesta de Gemini.")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON de Gemini: {str(e)}")
        raise Exception(f"Gemini devolvió una respuesta JSON inválida: {str(e)}")
    except Exception as e:
        logger.error(f"Error generando datos con Gemini: {str(e)}")
        raise Exception(f"Fallo en la generación de IA: {str(e)}")
