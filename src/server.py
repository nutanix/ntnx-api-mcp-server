"""Startup YAML loading and operation indexing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import Settings
from src.config.constants import ARTIFACT_FILENAME_SUFFIX
from src.generators import ToolGenerator
from src.parsers import NamespaceMetadata, OpenAPIParser, OperationInfo
from src.tools import RuntimeToolDispatcher


@dataclass(slots=True)
class StartupLoadResult:
    """Aggregated startup result for loaded operations."""

    artifacts_source: str
    artifact_directory: Path
    files: list[Path]
    operations: list[OperationInfo]
    namespace_tools: list[dict[str, Any]]
    discovery_tools: list[dict[str, Any]]
    operation_index: dict[str, dict[str, Any]]
    generator: ToolGenerator


def select_artifact_source(settings: Settings) -> tuple[str, Path]:
    """
    Select YAML source directory with deterministic precedence.

    Order:
    1) Runtime artifacts directory
    2) Bundled default specs directory
    3) Fail startup
    """
    runtime_files = list_yaml_artifacts(settings.artifacts_dir)
    if runtime_files:
        return ("runtime", settings.artifacts_dir)

    default_files = list_yaml_artifacts(settings.default_artifacts_dir)
    if default_files:
        return ("bundled", settings.default_artifacts_dir)

    raise RuntimeError(
        "No YAML artifacts found in runtime or bundled directories. "
        f"Checked: {settings.artifacts_dir} and {settings.default_artifacts_dir}"
    )


def list_yaml_artifacts(directory: Path) -> list[Path]:
    """List YAML files matching `*-all-documentation.yaml`."""
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{ARTIFACT_FILENAME_SUFFIX}"))


def infer_namespace(file_path: Path) -> str:
    """Infer namespace from `<namespace>-<version>-all-documentation.yaml`."""
    file_name = file_path.name
    first_dash = file_name.find("-")
    if first_dash <= 0:
        return "unknown"
    return file_name[:first_dash]


def load_operations_from_yamls(settings: Settings) -> StartupLoadResult:
    """Load all operations from selected YAML source.

    Collects component schemas and namespace display metadata from each spec file
    and passes them to ``ToolGenerator`` for schema resolution and tool description
    enrichment. Schema resolution itself is lazy (triggered by ``getOperationSchema``).
    """
    source_label, source_dir = select_artifact_source(settings)
    files = list_yaml_artifacts(source_dir)
    operations: list[OperationInfo] = []
    namespace_schemas: dict[str, dict[str, Any]] = {}
    namespace_metadata: dict[str, NamespaceMetadata] = {}

    for file_path in files:
        parser = OpenAPIParser(file_path)
        parser.load()
        namespace = infer_namespace(file_path)
        operations.extend(parser.extract_operations(namespace=namespace))
        namespace_schemas.setdefault(namespace, {}).update(parser.schemas)
        if namespace not in namespace_metadata:
            namespace_metadata[namespace] = parser.get_namespace_metadata(namespace)

    generator = ToolGenerator(
        operations,
        namespace_schemas=namespace_schemas,
        namespace_metadata=namespace_metadata,
    )
    namespace_tools = generator.build_namespace_tools()
    discovery_tools = generator.build_discovery_tools()
    operation_index = generator.build_operation_index()

    return StartupLoadResult(
        artifacts_source=source_label,
        artifact_directory=source_dir,
        files=files,
        operations=operations,
        namespace_tools=namespace_tools,
        discovery_tools=discovery_tools,
        operation_index=operation_index,
        generator=generator,
    )


def build_runtime_dispatcher(settings: Settings) -> RuntimeToolDispatcher:
    """Build runtime dispatcher using loaded YAML operations."""
    load_result = load_operations_from_yamls(settings)
    return RuntimeToolDispatcher(settings=settings, load_result=load_result)
