import unittest

from app.services.schema_retrieval import SchemaRetrievalService

SAMPLE_METADATA = {
    "database_type": "postgresql",
    "database_name": "app_db",
    "schemas": [
        {
            "name": "public",
            "tables": [
                {
                    "name": "users",
                    "primary_key": ["id"],
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "email", "type": "VARCHAR"},
                    ],
                    "foreign_keys": [],
                },
                {
                    "name": "orders",
                    "primary_key": ["id"],
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "user_id", "type": "INTEGER"},
                        {"name": "status", "type": "VARCHAR"},
                    ],
                    "foreign_keys": [
                        {
                            "columns": ["user_id"],
                            "referred_schema": "public",
                            "referred_table": "users",
                            "referred_columns": ["id"],
                        }
                    ],
                },
                {
                    "name": "products",
                    "primary_key": ["id"],
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "title", "type": "VARCHAR"},
                    ],
                    "foreign_keys": [],
                },
            ],
        }
    ],
    "relationships": [
        {
            "from_schema": "public",
            "from_table": "orders",
            "from_columns": ["user_id"],
            "to_schema": "public",
            "to_table": "users",
            "to_columns": ["id"],
        }
    ],
}


class FindRelevantTablesTest(unittest.TestCase):
    def test_ranks_table_matching_question_first(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.find_relevant_tables("show me all users")

        self.assertEqual(results[0]["table"], "users")
        self.assertEqual(results[0]["schema"], "public")

    def test_matches_on_column_name_too(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.find_relevant_tables("what is the status of orders")

        table_names = [result["table"] for result in results]
        self.assertIn("orders", table_names[:1])

    def test_falls_back_to_all_tables_when_nothing_matches(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.find_relevant_tables("xyzabc nonsense query")

        table_names = {result["table"] for result in results}
        self.assertEqual(table_names, {"users", "orders", "products"})


class GetColumnsTest(unittest.TestCase):
    def test_returns_columns_and_primary_key_for_requested_table(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.get_columns(["users"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["table"], "users")
        self.assertEqual(results[0]["primary_key"], ["id"])
        column_names = [column["name"] for column in results[0]["columns"]]
        self.assertEqual(column_names, ["id", "email"])

    def test_supports_schema_qualified_table_name(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.get_columns(["public.orders"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["table"], "orders")
        self.assertEqual(results[0]["schema"], "public")

    def test_omits_unknown_tables(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.get_columns(["does_not_exist"])

        self.assertEqual(results, [])


class GetRelationshipsTest(unittest.TestCase):
    def test_returns_relationships_touching_requested_tables(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.get_relationships(["orders", "users"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["from_table"], "orders")
        self.assertEqual(results[0]["to_table"], "users")

    def test_excludes_relationships_not_touching_requested_tables(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)

        results = service.get_relationships(["products"])

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
