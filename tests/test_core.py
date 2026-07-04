import unittest
from unittest.mock import patch
from skill_generador_datos.core import DataGenerator
from skill_generador_datos.schemas import DatabaseSchema, TableSchema, ColumnSchema, TableGenerationConfig

class TestDataGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = DataGenerator(locale="en_US")
        
        # Crear esquema simple
        user_table = TableSchema(
            name="users",
            columns=[
                ColumnSchema(name="id", data_type="int", is_primary_key=True),
                ColumnSchema(name="email", data_type="varchar", is_unique=True),
                ColumnSchema(name="name", data_type="varchar")
            ]
        )
        post_table = TableSchema(
            name="posts",
            columns=[
                ColumnSchema(name="id", data_type="int", is_primary_key=True),
                ColumnSchema(name="user_id", data_type="int", foreign_key={"table": "users", "column": "id"}),
                ColumnSchema(name="content", data_type="text")
            ]
        )
        self.schema = DatabaseSchema(
            database_name="test_db",
            motor="postgres",
            tables=[user_table, post_table]
        )

    @patch("skill_generador_datos.core.DataGenerator._try_generate_ai_seeds")
    def test_fallback_faker_generation(self, mock_try_generate_ai_seeds):
        # Asegurarnos de que el fallback a Faker se active devolviendo None en IA
        mock_try_generate_ai_seeds.return_value = None

        configs = [
            TableGenerationConfig(table_name="users", record_count=10),
            TableGenerationConfig(table_name="posts", record_count=15)
        ]

        result = self.generator.generate(schema=self.schema, table_configs=configs)

        self.assertIn("users", result)
        self.assertIn("posts", result)

        self.assertEqual(len(result["users"]["rows"]), 10)
        self.assertEqual(len(result["posts"]["rows"]), 15)
        
        # Validar PK uniqueness
        user_ids = [row[0] for row in result["users"]["rows"]]
        self.assertEqual(len(user_ids), len(set(user_ids)), "Las PKs generadas deben ser únicas")

        # Validar Foreign Keys
        post_user_ids = [row[1] for row in result["posts"]["rows"]]
        for p_uid in post_user_ids:
            self.assertIn(p_uid, user_ids, "Las FKs generadas deben existir en la tabla referenciada")

if __name__ == '__main__':
    unittest.main()
