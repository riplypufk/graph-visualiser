import tempfile
import unittest
from pathlib import Path

from src.main import ConfigError, validate_config


BASE = {
    "package_name": "curl",
    "repository": "https://example.org/alpine/main",
    "test_repository_mode": False,
    "package_version": "8.10.1-r0",
    "graph_image_file": "dependencies.png",
    "ascii_tree": True,
}


class ConfigValidationTests(unittest.TestCase):

    def test_valid_configuration(self):
        config = validate_config(BASE, Path.cwd())
        self.assertEqual(config.package_name, "curl")

    def test_package_name_error(self):
        data = {**BASE, "package_name": ""}
        with self.assertRaisesRegex(ConfigError, "package_name"):
            validate_config(data, Path.cwd())

    def test_repository_url_error(self):
        data = {**BASE, "repository": "not-a-url"}
        with self.assertRaisesRegex(ConfigError, "repository"):
            validate_config(data, Path.cwd())

    def test_test_repository_path_error(self):
        data = {
            **BASE,
            "repository": "./missing.txt",
            "test_repository_mode": True,
        }
        with self.assertRaisesRegex(ConfigError, "repository|Тестовый файл"):
            validate_config(data, Path.cwd())

    def test_test_repository_must_be_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            data = {
                **BASE,
                "repository": directory,
                "test_repository_mode": True,
            }
            with self.assertRaises(ConfigError):
                validate_config(data, Path.cwd())

    def test_test_mode_type_error(self):
        data = {**BASE, "test_repository_mode": "yes"}
        with self.assertRaisesRegex(ConfigError, "test_repository_mode"):
            validate_config(data, Path.cwd())

    def test_version_error(self):
        data = {**BASE, "package_version": ""}
        with self.assertRaisesRegex(ConfigError, "package_version"):
            validate_config(data, Path.cwd())

    def test_image_filename_error(self):
        data = {**BASE, "graph_image_file": "../graph.svg"}
        with self.assertRaisesRegex(ConfigError, "graph_image_file"):
            validate_config(data, Path.cwd())

    def test_ascii_tree_type_error(self):
        data = {**BASE, "ascii_tree": "true"}
        with self.assertRaisesRegex(ConfigError, "ascii_tree"):
            validate_config(data, Path.cwd())

    def test_missing_and_unknown_keys(self):
        data = {**BASE, "extra": 1}
        del data["package_name"]
        with self.assertRaises(ConfigError) as context:
            validate_config(data, Path.cwd())
        self.assertIn("package_name", str(context.exception))
        self.assertIn("extra", str(context.exception))


if __name__ == "__main__":
    unittest.main()
