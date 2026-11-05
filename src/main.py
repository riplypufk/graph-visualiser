from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml


REQUIRED_KEYS = {
    "package_name",
    "repository",
    "test_repository_mode",
    "package_version",
    "graph_image_file",
    "ascii_tree",
}

PACKAGE_PATTERN = r"[A-Za-z0-9+_.-]+"
VERSION_PATTERN = r"[A-Za-z0-9+_.:~-]+"


@dataclass(frozen=True)
class Config:
    package_name: str
    repository: str
    test_repository_mode: bool
    package_version: str
    graph_image_file: str
    ascii_tree: bool


class ConfigError(Exception):
    """Ошибка чтения или проверки конфигурации."""


def validate_package_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        message = (
            "Параметр 'package_name' должен быть непустой строкой."
        )
        raise ConfigError(message)

    value = value.strip()

    if not re.fullmatch(PACKAGE_PATTERN, value):
        message = (
            "Параметр 'package_name' содержит недопустимые символы."
        )
        raise ConfigError(message)

    return value


def validate_version(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        message = (
            "Параметр 'package_version' должен быть непустой строкой."
        )
        raise ConfigError(message)

    value = value.strip()

    if not re.fullmatch(VERSION_PATTERN, value):
        message = (
            "Параметр 'package_version' содержит недопустимые символы."
        )
        raise ConfigError(message)

    return value


def validate_boolean(value: object, key: str) -> bool:
    if type(value) is not bool:
        raise ConfigError(
            f"Параметр '{key}' должен быть true или false."
        )

    return value


def validate_image_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        message = (
            "Параметр 'graph_image_file' не должен быть пустым."
        )
        raise ConfigError(message)

    value = value.strip()

    invalid_path = Path(value).name != value
    invalid_extension = not value.lower().endswith(".png")

    if invalid_path or invalid_extension:
        message = (
            "Параметр 'graph_image_file' должен быть именем PNG-файла."
        )
        raise ConfigError(message)

    return value


def validate_repository(
    value: object,
    test_mode: bool,
    config_dir: Path,
) -> str:
    if not isinstance(value, str) or not value.strip():
        message = "Параметр 'repository' должен быть непустой строкой."
        raise ConfigError(message)

    value = value.strip()

    if test_mode:
        validate_test_file(value, config_dir)
    else:
        validate_repository_url(value)

    return value


def validate_test_file(value: str, config_dir: Path) -> None:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = config_dir / path

    if not path.exists():
        raise ConfigError(
            f"Тестовый файл репозитория не найден: {path}"
        )

    if not path.is_file():
        message = (
            "В параметре 'repository' требуется путь к файлу."
        )
        raise ConfigError(message)


def validate_repository_url(value: str) -> None:
    parsed = urlparse(value)
    valid_scheme = parsed.scheme in {"http", "https"}

    if not valid_scheme or not parsed.netloc:
        message = (
            "Параметр 'repository' должен быть HTTP(S) URL."
        )
        raise ConfigError(message)


def check_keys(data: dict) -> None:
    missing = REQUIRED_KEYS - data.keys()
    unknown = data.keys() - REQUIRED_KEYS
    errors = []

    errors.extend(
        f"Отсутствует параметр: {key}"
        for key in sorted(missing)
    )

    errors.extend(
        f"Неизвестный параметр: {key}"
        for key in sorted(unknown)
    )

    if errors:
        raise ConfigError("\n".join(errors))


def validate_config(data: object, config_dir: Path) -> Config:
    if not isinstance(data, dict):
        message = "YAML должен содержать набор ключей и значений."
        raise ConfigError(message)

    check_keys(data)

    test_mode = validate_boolean(
        data["test_repository_mode"],
        "test_repository_mode",
    )

    return Config(
        package_name=validate_package_name(data["package_name"]),
        repository=validate_repository(
            data["repository"],
            test_mode,
            config_dir,
        ),
        test_repository_mode=test_mode,
        package_version=validate_version(data["package_version"]),
        graph_image_file=validate_image_name(data["graph_image_file"]),
        ascii_tree=validate_boolean(
            data["ascii_tree"],
            "ascii_tree",
        ),
    )


def load_config(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"Файл конфигурации не найден: {path}")

    if not path.is_file():
        message = (
            f"Путь конфигурации не является файлом: {path}"
        )
        raise ConfigError(message)

    try:
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)

    except yaml.YAMLError as error:
        raise ConfigError(
            f"Некорректный YAML: {error}"
        ) from error

    except OSError as error:
        message = f"Не удалось прочитать конфигурацию: {error}"
        raise ConfigError(message) from error

    return validate_config(data, path.resolve().parent)


def print_config(config: Config) -> None:
    print("Параметры конфигурации:")
    print(f"package_name: {config.package_name}")
    print(f"repository: {config.repository}")

    test_mode = str(config.test_repository_mode).lower()
    print(f"test_repository_mode: {test_mode}")

    print(f"package_version: {config.package_version}")
    print(f"graph_image_file: {config.graph_image_file}")

    ascii_mode = str(config.ascii_tree).lower()
    print(f"ascii_tree: {ascii_mode}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Визуализатор зависимостей: этап 1."
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="путь к YAML-конфигурации",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        config = load_config(args.config)

    except ConfigError as error:
        print(
            f"Ошибка конфигурации:\n{error}",
            file=sys.stderr,
        )
        return 2

    print_config(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())