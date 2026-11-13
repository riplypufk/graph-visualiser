from __future__ import annotations

import gzip
import io
import tarfile
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APKINDEX_KEY_LENGTH = 1
APKINDEX_SEPARATOR_POSITION = 1
APKINDEX_VALUE_START = 2


class DependencyError(Exception):
    """Ошибка получения или разбора информации о зависимостях."""


@dataclass(frozen=True)
class PackageInfo:
    name: str
    version: str
    dependencies: tuple[str, ...]


def build_apkindex_url(repository: str) -> str:
    repository = repository.rstrip("/")

    if repository.endswith("APKINDEX.tar.gz"):
        return repository

    return f"{repository}/APKINDEX.tar.gz"


def download_apkindex(repository: str) -> bytes:
    """Скачивает APKINDEX.tar.gz из репозитория."""
    url = build_apkindex_url(repository)

    request = Request(
        url,
        headers={
            "User-Agent": "dependency-graph-visualizer/1.0",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            return response.read()

    except HTTPError as error:
        raise DependencyError(
            f"Не удалось получить APKINDEX: "
            f"HTTP {error.code} для {url}"
        ) from error

    except URLError as error:
        raise DependencyError(
            f"Не удалось подключиться к репозиторию: {error.reason}"
        ) from error

    except OSError as error:
        raise DependencyError(
            f"Ошибка загрузки APKINDEX: {error}"
        ) from error


def decompress_gzip(data: bytes) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as file:
            return file.read()
    except (gzip.BadGzipFile, EOFError) as error:
        raise DependencyError(
            "Полученный APKINDEX.tar.gz имеет некорректный формат gzip."
        ) from error


def extract_index_from_tar(data: bytes) -> bytes:
    try:
        with tarfile.open(
            fileobj=io.BytesIO(data),
            mode="r:",
        ) as archive:
            member = archive.getmember("APKINDEX")
            extracted = archive.extractfile(member)

            if extracted is None:
                raise DependencyError(
                    "В APKINDEX.tar.gz отсутствует файл APKINDEX."
                )

            return extracted.read()

    except tarfile.TarError as error:
        raise DependencyError(
            "Полученный APKINDEX.tar.gz имеет некорректный формат tar."
        ) from error
    except KeyError as error:
        raise DependencyError(
            "В APKINDEX.tar.gz отсутствует файл APKINDEX."
        ) from error


def extract_apkindex(data: bytes) -> str:
    decompressed = decompress_gzip(data)
    extracted = extract_index_from_tar(decompressed)

    try:
        return extracted.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DependencyError(
            "Файл APKINDEX содержит данные в неподдерживаемой кодировке."
        ) from error


def parse_dependencies(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()

    dependencies = []

    for dependency in value.split():
        dependency = dependency.strip()

        if dependency:
            dependencies.append(dependency)

    return tuple(dependencies)


def create_package(fields: dict) -> PackageInfo | None:
    name = fields.get("P")
    version = fields.get("V")

    if name is None or version is None:
        return None

    return PackageInfo(
        name=name,
        version=version,
        dependencies=fields.get("D", ()),
    )


def parse_apkindex_line(
    line: str,
    fields: dict,
) -> None:
    if len(line) <= APKINDEX_SEPARATOR_POSITION:
        return

    if line[APKINDEX_SEPARATOR_POSITION] != ":":
        return

    key = line[0]
    value = line[APKINDEX_VALUE_START:].strip()

    if key == "P":
        fields["P"] = value
    elif key == "V":
        fields["V"] = value
    elif key == "D":
        fields["D"] = parse_dependencies(value)


def parse_apkindex(index: str) -> list[PackageInfo]:
    packages = []
    fields = {}

    for raw_line in index.splitlines():
        line = raw_line.strip()

        if not line:
            package = create_package(fields)
            if package is not None:
                packages.append(package)
            fields = {}
            continue

        parse_apkindex_line(line, fields)

    package = create_package(fields)
    if package is not None:
        packages.append(package)

    return packages

def find_package(
    packages: list[PackageInfo],
    package_name: str,
    package_version: str,
) -> PackageInfo:
    for package in packages:
        if (
            package.name == package_name
            and package.version == package_version
        ):
            return package

    raise DependencyError(
        f"Пакет '{package_name}' версии '{package_version}' "
        "не найден в APKINDEX."
    )


def get_direct_dependencies(
    repository: str,
    package_name: str,
    package_version: str,
) -> tuple[str, ...]:
    data = download_apkindex(repository)
    index = extract_apkindex(data)
    packages = parse_apkindex(index)

    package = find_package(
        packages,
        package_name,
        package_version,
    )

    return package.dependencies