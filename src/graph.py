
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.dependencies import PackageInfo, find_package


class GraphError(Exception):
    pass


@dataclass(frozen=True)
class DependencyGraph:
    dependencies: dict[str, tuple[str, ...]]

    @property
    def nodes(self) -> tuple[str, ...]:
        result = []

        for package, dependencies in self.dependencies.items():
            if package not in result:
                result.append(package)

            for dependency in dependencies:
                if dependency not in result:
                    result.append(dependency)

        return tuple(result)


def read_repository_file(path: str | Path) -> list[str]:
    repository_path = Path(path)

    if not repository_path.exists():
        raise GraphError(
            f"Тестовый репозиторий не найден: {repository_path}"
        )

    if not repository_path.is_file():
        raise GraphError(
            "Путь тестового репозитория не является файлом."
        )

    try:
        return repository_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as error:
        raise GraphError(
            f"Не удалось прочитать репозиторий: {error}"
        ) from error


def parse_repository_line(
    raw_line: str,
    line_number: int,
) -> tuple[str, tuple[str, ...]] | None:
    line = raw_line.strip()

    if not line or line.startswith("#"):
        return None

    if "->" in line:
        package, dependencies = line.split("->", maxsplit=1)
    elif ":" in line:
        package, dependencies = line.split(":", maxsplit=1)
    else:
        raise GraphError(
            f"Некорректная строка {line_number}: {raw_line}"
        )

    package = package.strip()

    validate_package_name(package)

    parsed_dependencies = parse_repository_dependencies(
        dependencies,
        line_number,
    )

    return package, parsed_dependencies


def validate_package_name(package: str) -> None:
    if not re.fullmatch(r"[A-Z]+", package):
        raise GraphError(
            f"Некорректное имя пакета: {package}"
        )


def parse_repository_dependencies(
    dependencies_text: str,
    line_number: int,
) -> tuple[str, ...]:
    dependencies = tuple(dependencies_text.split())

    for dependency in dependencies:
        if not re.fullmatch(r"[A-Z]+", dependency):
            raise GraphError(
                f"Некорректная зависимость {dependency} "
                f"в строке {line_number}."
            )

    return dependencies


def validate_unique_package(
    package: str,
    repository: dict[str, tuple[str, ...]],
) -> None:
    if package in repository:
        raise GraphError(
            f"Пакет {package} объявлен несколько раз."
        )


def validate_repository_dependencies_exist(
    repository: dict[str, tuple[str, ...]],
) -> None:
    for package, dependencies in repository.items():
        for dependency in dependencies:
            if dependency not in repository:
                raise GraphError(
                    f"Пакет {package} зависит от {dependency}, "
                    "но он не описан в репозитории."
                )


def parse_test_repository(
    path: str | Path,
) -> dict[str, tuple[str, ...]]:
    lines = read_repository_file(path)
    repository = {}

    for line_number, raw_line in enumerate(lines, start=1):
        parsed = parse_repository_line(raw_line, line_number)

        if parsed is None:
            continue

        package, dependencies = parsed

        validate_unique_package(package, repository)

        repository[package] = dependencies

    validate_repository_dependencies_exist(repository)

    return repository


def build_graph_recursive_bfs(
    root_package: str,
    get_dependencies: Callable[[str], tuple[str, ...]],
) -> DependencyGraph:
    if not root_package:
        raise GraphError("Не задан корневой пакет.")
    graph = {}
    visited = set()
    def process_queue(queue: list[str]) -> None:
        if not queue:
            return
        package = queue.pop(0)
        if package in visited:
            process_queue(queue)
            return
        visited.add(package)
        try:
            dependencies = get_dependencies(package)
        except Exception as error:
            raise GraphError(
                f"Не удалось получить зависимости пакета "
                f"{package}: {error}"
            ) from error
        unique_dependencies = tuple(dict.fromkeys(dependencies))
        graph[package] = unique_dependencies

        for dependency in unique_dependencies:
            if dependency not in visited and dependency not in queue:
                queue.append(dependency)
        process_queue(queue)
    process_queue([root_package])
    return DependencyGraph(graph)


def build_test_graph(
    root_package: str,
    repository_path: str | Path,
) -> DependencyGraph:

    repository = parse_test_repository(repository_path)

    if root_package not in repository:
        raise GraphError(
            f"Пакет {root_package} отсутствует в репозитории."
        )

    return build_graph_recursive_bfs(
        root_package,
        lambda package: repository[package],
    )


def split_dependency(value: str) -> tuple[str, str, str]:
    match = re.match(
        r"^(.*?)(>=|<=|=|>|<|~|<~|>~)(.+)$",
        value.strip(),
    )

    if match:
        return (
            match.group(1),
            match.group(2),
            match.group(3),
        )

    return value.strip(), "", ""


def find_named_packages(
    dependency_name: str,
    packages: list[PackageInfo],
) -> list[PackageInfo]:
    return [
        package
        for package in packages
        if package.name == dependency_name
    ]


def find_provided_packages(
    dependency_name: str,
    packages: list[PackageInfo],
) -> list[PackageInfo]:
    result = []

    for package in packages:
        for provided in package.provides:
            provided_name = split_dependency(provided)[0]

            if provided_name == dependency_name:
                result.append(package)
                break

    return result


def find_candidates(
    dependency_name: str,
    packages: list[PackageInfo],
) -> list[PackageInfo]:
    candidates = find_named_packages(
        dependency_name,
        packages,
    )

    if candidates:
        return candidates

    return find_provided_packages(
        dependency_name,
        packages,
    )


def validate_candidates(
    dependency_name: str,
    candidates: list[PackageInfo],
) -> None:
    if candidates:
        return

    if ":" in dependency_name:
        return

    raise GraphError(
        f"Пакет-зависимость {dependency_name} "
        "не найден в APKINDEX."
    )


def filter_by_version(
    candidates: list[PackageInfo],
    dependency_name: str,
    required_version: str,
) -> list[PackageInfo]:
    result = [
        package
        for package in candidates
        if package.version == required_version
    ]

    if not result:
        raise GraphError(
            f"Не найдена версия {required_version} "
            f"пакета {dependency_name}."
        )

    return result


def select_unique_package(
    candidates: list[PackageInfo],
    dependency_name: str,
) -> PackageInfo:
    if len(candidates) > 1:
        raise GraphError(
            f"Для зависимости {dependency_name} найдено "
            "несколько возможных пакетов. "
            "Однозначный выбор не реализован."
        )

    return candidates[0]


def resolve_package(
    dependency: str,
    packages: list[PackageInfo],
) -> PackageInfo | None:
    dependency_name, operator, required_version = (
        split_dependency(dependency)
    )

    if dependency_name.startswith("/"):
        return None

    candidates = find_candidates(
        dependency_name,
        packages,
    )

    validate_candidates(dependency_name, candidates)

    if not candidates:
        return None

    if operator == "=":
        candidates = filter_by_version(
            candidates,
            dependency_name,
            required_version,
        )

    return select_unique_package(
        candidates,
        dependency_name,
    )


def _load_root_package(
    repository: str,
    package_name: str,
    package_version: str,
) -> tuple[list[PackageInfo], PackageInfo]:
    from src.dependencies import load_repository_packages

    try:
        packages = load_repository_packages(repository)
        root = find_package(packages, package_name, package_version)
    except Exception as error:
        raise GraphError(
            f"Не удалось загрузить корневой пакет: {error}"
        ) from error

    return packages, root


def _resolve_direct_dependencies(
    package: PackageInfo,
    packages: list[PackageInfo],
    selected_packages: dict[str, PackageInfo],
) -> tuple[str, ...]:
    dependencies: list[str] = []

    for raw_dependency in package.dependencies:
        resolved = resolve_package(raw_dependency, packages)
        if resolved is None:
            continue

        previous = selected_packages.get(resolved.name)
        if previous is not None and previous.version != resolved.version:
            raise GraphError(
                f"Для пакета {resolved.name} требуются разные версии."
            )

        selected_packages[resolved.name] = resolved
        dependencies.append(resolved.name)

    return tuple(dict.fromkeys(dependencies))

def build_real_dependency_graph(
    repository: str,
    package_name: str,
    package_version: str,
) -> DependencyGraph:
    packages, root = _load_root_package(
        repository,
        package_name,
        package_version,
    )
    selected_packages = {root.name: root}

    return build_graph_recursive_bfs(
        package_name,
        lambda name: _resolve_direct_dependencies(
            selected_packages[name],
            packages,
            selected_packages,
        ),
    )