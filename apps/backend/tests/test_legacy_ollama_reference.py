"""The frozen Ollama reference remains complete enough for later comparison."""

import unittest
from pathlib import Path


class LegacyOllamaReferenceTest(unittest.TestCase):
    root = Path(__file__).parents[1] / "legacy" / "ollama"

    def test_reference_sources_are_entirely_commented(self):
        references = sorted(self.root.glob("*.reference.*"))
        self.assertEqual(len(references), 10)
        for path in references:
            with self.subTest(path=path.name):
                lines = path.read_text(encoding="utf-8").splitlines()
                self.assertTrue(lines)
                self.assertTrue(all(line.startswith("#") for line in lines))

    def test_historical_transport_prompts_and_options_are_preserved(self):
        preserved = "\n".join(
            path.read_text(encoding="utf-8") for path in self.root.glob("*.reference.*")
        )
        for marker in (
            "/api/chat",
            "/api/tags",
            "ollama pull",
            "OLLAMA_BASE_URL",
            "qwen3:1.7b",
            "num_ctx",
            "num_predict",
            "keep_alive",
            "Eres el motor privado de interpretación literaria de LibrIA",
            "Selecciona cuatro libros diferentes del catálogo",
            "Construye un perfil LITERARIO GLOBAL",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, preserved)


if __name__ == "__main__":
    unittest.main()
