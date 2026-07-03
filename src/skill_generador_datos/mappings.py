"""
generators/faker_mappings.py
Mapeo de nombres de columnas y tipos de datos a métodos de Faker.
CONTEXTO-CONSCIENTE: usa el nombre de la tabla para decidir qué generar.
"""
import re
import random
from typing import Callable, Any, Optional
from faker import Faker

# ─────────────────────────────────────────────
# Catálogos estáticos para columnas específicas
# ─────────────────────────────────────────────

PRODUCT_NAMES = [
    "Laptop HP Pavilion 15", "Monitor LG UltraWide 34\"", "Teclado Mecánico Logitech G Pro",
    "Mouse Inalámbrico Logitech MX Master 3", "Auriculares Sony WH-1000XM5",
    "Cámara Canon EOS R5", "Tablet Samsung Galaxy Tab S9", "Impresora Epson EcoTank L3250",
    "SSD Samsung 970 EVO 1TB", "Router TP-Link Archer AX73", "Webcam Logitech C920",
    "Disco Duro Externo WD 2TB", "Parlante JBL Flip 6", "Smartwatch Apple Watch SE",
    "Cargador USB-C Anker 65W", "Cable HDMI 2.1 4K", "Memoria RAM Kingston 16GB DDR5",
    "Procesador AMD Ryzen 7 7800X3D", "Tarjeta Gráfica NVIDIA RTX 4070",
    "Fuente de Poder Corsair 750W", "Silla Gamer Cougar Armor One", "Mochila para Laptop 15.6\"",
    "Hub USB-C 7 en 1", "Micrófono Blue Yeti", "Soporte para Monitor Ergonómico",
    "Alfombrilla de Mouse XL", "Cooler para Laptop", "UPS APC 1500VA",
    "Proyector Epson PowerLite", "Lector de Tarjetas SD USB 3.0",
]

CATEGORIES = [
    "Electrónica", "Hogar", "Deportes", "Ropa", "Tecnología", "Juguetes", "Libros",
    "Cocina", "Jardín", "Mascotas", "Salud", "Belleza", "Automotriz", "Oficina",
    "Música", "Fotografía", "Gaming", "Accesorios", "Herramientas", "Iluminación",
    "Audio", "Video", "Computación", "Celulares", "Tablets", "Almacenamiento",
    "Redes", "Software", "Periféricos", "Mobiliario",
]

PROJECT_NAMES = [
    "Portal Web Corporativo", "App de Inventario", "Sistema de Facturación",
    "Dashboard Analytics", "API de Pagos", "Módulo de Reportes",
    "Plataforma E-commerce", "Sistema CRM", "App de Gestión de Tareas",
    "Migración de Base de Datos", "Chatbot de Soporte", "Panel de Administración",
    "Sistema de Reservas", "App de Seguimiento GPS", "Plataforma de Capacitación",
]

TITLES = [
    "Guía de Instalación", "Manual de Usuario", "Reporte Mensual", "Plan de Proyecto",
    "Especificación Técnica", "Acta de Reunión", "Propuesta Comercial",
    "Análisis de Requerimientos", "Documento de Diseño", "Informe de Pruebas",
]

ROLES = ["admin", "editor", "viewer", "moderator", "owner", "member", "guest", "contributor"]
STATUSES = ["activo", "inactivo", "pendiente", "completado", "cancelado", "en_progreso", "archivado"]

# ─────────────────────────────────────────────
# Regex rules para nombres de columna
# El orden importa: los primeros matches tienen prioridad.
# ─────────────────────────────────────────────
NAME_MAPPINGS = [
    (r"(?i)email|correo", "email"),
    (r"(?i)^first_name$|^primer_nombre$", "first_name"),
    (r"(?i)^last_name$|^apellido$", "last_name"),
    (r"(?i)full_name|nombre_completo", "name"),
    (r"(?i)phone|telefono|tel\b", "phone_number"),
    (r"(?i)address|direccion", "address"),
    (r"(?i)city|ciudad", "city"),
    (r"(?i)country|pais", "country"),
    (r"(?i)zip|postal|cp", "postcode"),
    (r"(?i)company|empresa", "company"),
    (r"(?i)job|profesion|puesto", "job"),
    (r"(?i)date_of_birth|dob|fecha_nacimiento", "date_of_birth"),
    (r"(?i)date|fecha", "date"),
    (r"(?i)time|hora", "time"),
    (r"(?i)uuid|guid", "uuid4"),
    (r"(?i)password|clave|pwd", "password"),
    (r"(?i)url|website|web", "url"),
    (r"(?i)ip|ip_address", "ipv4"),
    (r"(?i)color", "color_name"),
    (r"(?i)iban", "iban"),
    (r"(?i)credit_card|tarjeta", "credit_card_number"),
    (r"(?i)price|precio|amount|monto|total|costo|cost|valor|value", "pyfloat"),
    (r"(?i)quantity|cantidad|qty|stock|inventory|inventario", "random_int"),
    (r"(?i)description|descripcion|bio|notes|notas", "sentence"),
    (r"(?i)status|estado", "_status"),
    (r"(?i)role?$|rol$", "_role"),
    (r"(?i)categor", "_category"),
    (r"(?i)titulo|title", "_title"),
]

# Mapping by generic SQL types
TYPE_MAPPINGS = {
    "VARCHAR": "word",
    "CHARACTER VARYING": "word",
    "CHAR": "random_letter",
    "TEXT": "sentence",
    "INT": "random_int",
    "INTEGER": "random_int",
    "BIGINT": "random_number",
    "SMALLINT": "random_int",
    "TINYINT": "boolean",
    "FLOAT": "pyfloat",
    "DOUBLE": "pyfloat",
    "DOUBLE PRECISION": "pyfloat",
    "REAL": "pyfloat",
    "DECIMAL": "pyfloat",
    "NUMERIC": "pyfloat",
    "DATE": "date",
    "DATETIME": "date_time",
    "TIMESTAMP": "date_time",
    "TIMESTAMP WITH TIME ZONE": "date_time",
    "TIMESTAMP WITHOUT TIME ZONE": "date_time",
    "TIMESTAMPTZ": "date_time",
    "TIME": "time",
    "TIME WITH TIME ZONE": "time",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "JSON": "json",
    "JSONB": "json",
    "UUID": "uuid4",
    "BYTEA": "binary",
}

# ─────────────────────────────────────────────
# Tablas cuyo "nombre" NO es de persona
# ─────────────────────────────────────────────
NON_PERSON_TABLES = {
    "producto", "productos", "product", "products",
    "item", "items", "articulo", "articulos",
    "project", "projects", "proyecto", "proyectos",
    "categoria", "categorias", "category", "categories",
    "servicio", "servicios", "service", "services",
    "documento", "documentos", "document", "documents",
    "curso", "cursos", "course", "courses",
    "evento", "eventos", "event", "events",
    "diagrama", "diagramas", "diagram", "diagrams",
    "tarea", "tareas", "task", "tasks",
    "ticket", "tickets",
    "empresa", "empresas",
    "tienda", "tiendas", "store", "stores",
}


def _detect_nombre_context(table_name: str) -> str:
    """
    Determina qué tipo de 'nombre' generar según el contexto de la tabla.
    Retorna: 'product', 'project', 'category', 'person', o 'generic'.
    """
    t = table_name.lower().strip()
    if t in {"producto", "productos", "product", "products", "item", "items", "articulo", "articulos"}:
        return "product"
    if t in {"project", "projects", "proyecto", "proyectos"}:
        return "project"
    if t in {"categoria", "categorias", "category", "categories"}:
        return "category"
    if t in {"servicio", "servicios", "service", "services"}:
        return "generic"
    if t in {"curso", "cursos", "course", "courses", "evento", "eventos", "event", "events"}:
        return "generic"
    if t in {"usuario", "usuarios", "user", "users", "persona", "personas", "empleado", "empleados",
             "cliente", "clientes", "customer", "customers", "contacto", "contactos",
             "collaborator", "collaborators", "colaborador", "colaboradores", "member", "members"}:
        return "person"
    # Default: si no sabemos, tratamos como nombre genérico (no de persona)
    if t in NON_PERSON_TABLES:
        return "generic"
    return "person"


def get_faker_method_for_column(
    fake: Faker,
    column_name: str,
    data_type: str,
    table_name: str = "",
) -> Callable[[], Any]:
    """
    Determina qué método de Faker usar para una columna basándose
    en su nombre, tipo de dato, Y el contexto de la tabla.
    """
    col_lower = column_name.lower().strip()
    table_lower = table_name.lower().strip()

    # ─── CASO ESPECIAL: columna "nombre" depende de la tabla ───
    if col_lower in ("nombre", "name", "nombre_producto", "product_name"):
        context = _detect_nombre_context(table_lower)
        if context == "product":
            return lambda: random.choice(PRODUCT_NAMES)
        elif context == "project":
            return lambda: random.choice(PROJECT_NAMES)
        elif context == "category":
            return lambda: random.choice(CATEGORIES)
        elif context == "person":
            return fake.name
        else:
            # Genérico: usa una frase corta tipo título
            return lambda: fake.catch_phrase()

    # ─── Regex-based mappings (excluir 'nombre' que ya se maneja arriba) ───
    for pattern, method_name in NAME_MAPPINGS:
        if re.search(pattern, column_name):
            # Precio: devolver float positivo con 2 decimales
            if method_name == "pyfloat":
                return lambda: round(fake.pyfloat(left_digits=4, right_digits=2, positive=True, min_value=0.01, max_value=9999.99), 2)
            # Stock/cantidad: entero positivo pequeño
            if method_name == "random_int":
                return lambda: fake.random_int(min=0, max=1000)
            # Categoría: usar catálogo estático
            if method_name == "_category":
                return lambda: random.choice(CATEGORIES)
            # Status: usar catálogo estático
            if method_name == "_status":
                return lambda: random.choice(STATUSES)
            # Role: usar catálogo estático
            if method_name == "_role":
                return lambda: random.choice(ROLES)
            # Título: usar catálogo estático
            if method_name == "_title":
                return lambda: random.choice(TITLES)
            # Descripciones: frase corta, NO párrafos largos
            if method_name == "sentence":
                return lambda: fake.sentence(nb_words=8)
            if hasattr(fake, method_name):
                return getattr(fake, method_name)

    # ─── Intentar por tipo de dato ───
    base_type = data_type.split('(')[0].upper().strip()
    method_name = TYPE_MAPPINGS.get(base_type)
    if method_name:
        # TEXT y sentence: generar frases cortas, no párrafos largos
        if method_name == "sentence":
            return lambda: fake.sentence(nb_words=8)
        if hasattr(fake, method_name):
            return getattr(fake, method_name)

    # ─── Fallback ───
    if any(t in base_type for t in ("INT", "NUM", "SERIAL", "REAL", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC")):
        return lambda: round(fake.pyfloat(left_digits=4, right_digits=2, positive=True), 2)
    return lambda: fake.word()
