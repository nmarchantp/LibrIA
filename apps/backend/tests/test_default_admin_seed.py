"""Contrato estático de la biblioteca inicial del administrador."""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from scripts.seed_default_admin import MANIFEST, seed_default_admin, stable_id


class DefaultAdminSeedContractTest(unittest.TestCase):
    @patch('scripts.migrate_and_seed.command.upgrade')
    @patch('scripts.migrate_and_seed.seed_default_admin')
    @patch('scripts.migrate_and_seed.get_settings')
    def test_fresh_migration_command_uses_account_only_with_discovery(self, settings, seed, upgrade):
        from scripts.migrate_and_seed import main
        settings.return_value.catalog_discovery_enabled = True
        with patch('sys.argv', ['migrate_and_seed']):
            main()
        seed.assert_called_once_with(['--account-only'])
        self.assertEqual(upgrade.call_args.args[1], 'head')

    @patch('scripts.migrate_and_seed.command.upgrade')
    @patch('scripts.migrate_and_seed.seed_default_admin')
    @patch('scripts.migrate_and_seed.get_settings')
    def test_migration_command_preserves_an_explicit_catalog_map(self, settings, seed, upgrade):
        from scripts.migrate_and_seed import main
        settings.return_value.catalog_discovery_enabled = True
        with patch('sys.argv', ['migrate_and_seed', '--catalog-map', 'selected-editions.json']):
            main()
        seed.assert_called_once_with(['--catalog-map', 'selected-editions.json'])

    def test_manifest_has_ten_unique_rated_and_reviewed_books(self):
        books = MANIFEST["books"]
        self.assertEqual(len(books), 10)
        self.assertEqual(len({book["key"] for book in books}), 10)
        self.assertEqual(len({book["title"].casefold() for book in books}), 10)
        self.assertEqual(
            {book["title"] for book in books},
            {
                "Harry Potter y la piedra filosofal",
                "Harry Potter y la cámara de los secretos",
                "Una corte de rosas y espinas",
                "Asesino de brujas",
                "Érase una vez un corazón roto",
                "Verity",
                "El reino de los malditos",
                "Caraval",
                "De sangre y cenizas",
                "El trono de los caídos",
            },
        )
        for book in books:
            rating = Decimal(str(book["rating"]))
            self.assertGreaterEqual(rating, Decimal("4"))
            self.assertLessEqual(rating, Decimal("5"))
            self.assertEqual(rating % Decimal("0.25"), 0)
            self.assertTrue(book["review"].strip())
            self.assertLessEqual(len(book["review"]), 3000)
            self.assertGreater(book["pages"], 0)

    def test_entity_ids_are_stable_and_separated_by_type(self):
        book = MANIFEST["books"][0]
        self.assertEqual(stable_id(f"work:{book['key']}"), stable_id(f"work:{book['key']}"))
        self.assertNotEqual(stable_id(f"work:{book['key']}"), stable_id(f"review:{book['key']}"))

    @patch("scripts.seed_default_admin._ensure_catalog_book")
    @patch("scripts.seed_default_admin.seed_demo_accounts")
    def test_account_only_does_not_touch_catalog_or_library(self, seed_accounts, ensure_catalog):
        db = MagicMock()
        result = seed_default_admin(db, "test-password", account_only=True)
        seed_accounts.assert_called_once_with(db, "test-password", keys={"admin"})
        ensure_catalog.assert_not_called()
        db.assert_not_called()
        self.assertEqual(db.mock_calls, [])
        self.assertEqual(result["books"], 0)
        self.assertEqual(result["reviews"], 0)

    @patch("scripts.seed_default_admin._ensure_catalog_book")
    @patch("scripts.seed_default_admin._ensure_finished_reading")
    @patch("scripts.seed_default_admin._ensure_review")
    @patch("scripts.seed_default_admin.seed_demo_accounts")
    def test_seed_requests_only_the_admin_account(
        self, seed_accounts, ensure_review, ensure_reading, ensure_catalog
    ):
        work, edition = MagicMock(), MagicMock()
        ensure_catalog.return_value = (work, edition)
        db = MagicMock()
        result = seed_default_admin(db, "test-password")
        seed_accounts.assert_called_once_with(db, "test-password", keys={"admin"})
        self.assertEqual(ensure_catalog.call_count, 10)
        self.assertEqual(ensure_reading.call_count, 10)
        self.assertEqual(ensure_review.call_count, 10)
        self.assertEqual(result["books"], 10)


if __name__ == "__main__":
    unittest.main()
