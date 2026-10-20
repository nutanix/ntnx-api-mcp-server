"""Discovery must use the same namespace as the corresponding executor."""

from pathlib import Path

import pytest
import yaml

from src.config import Settings
from src.server import build_runtime_dispatcher


@pytest.fixture
def dispatcher(tmp_path: Path):
    for namespace, path, parameter, field in (
        ("clustermgmt", "/clustermgmt/v4.0/config/disks/{extId}", "extId", "clusterName"),
        ("vmm", "/vmm/v4.0/ahv/config/vms/{vmExtId}/disks/{extId}", "vmExtId", "vmName"),
    ):
        operation = {
            "operationId": "getDiskById",
            "parameters": [
                {"name": parameter, "in": "path", "required": True, "schema": {"type": "string"}},
            ],
            "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Disk"}}}},
            "x-codeSamples": [{"lang": "python", "source": f"print('{namespace}')"}],
            "x-permissions": {"operationName": f"View {namespace} disk"},
        }
        spec = {
            "openapi": "3.0.0",
            "paths": {
                path: {"get": operation},
                f"/{namespace}/disks": {"post": {**operation, "operationId": f"create{namespace}Disk"}},
            },
            "components": {"schemas": {
                "Disk": {"type": "object", "properties": {field: {"$ref": "#/components/schemas/Name"}}},
                "Name": {"type": "string", "enum": [namespace]},
            }},
        }
        (tmp_path / f"{namespace}-v4.0-all-documentation.yaml").write_text(
            yaml.safe_dump(spec), encoding="utf-8",
        )
    return build_runtime_dispatcher(Settings(
        pc_host=None, artifacts_dir=tmp_path, default_artifacts_dir=tmp_path / "defaults",
    ))


@pytest.mark.parametrize("namespaces", [("clustermgmt", "vmm"), ("vmm", "clustermgmt")])
def test_scoped_schemas_and_cache_stay_in_their_namespace(dispatcher, namespaces):
    for namespace in (*namespaces, *namespaces):
        result = dispatcher.call_tool("getOperationSchema", {
            "operation": "getDiskById", "namespace": namespace,
        })
        assert result.ok, result.error
        schema = result.payload
        assert schema["namespace"] == namespace
        assert schema["path"].startswith(f"/{namespace}/")
        parameter = "vmExtId" if namespace == "vmm" else "extId"
        assert schema["path_parameters"][0]["name"] == parameter
        field = "vmName" if namespace == "vmm" else "clusterName"
        assert schema["request_body_schema"] == {field: {"type": "string", "enum": [namespace]}}


@pytest.mark.parametrize("namespace", ["clustermgmt", "vmm"])
def test_unique_operation_uses_its_own_component_definitions(dispatcher, namespace):
    result = dispatcher.call_tool("getOperationSchema", {"operation": f"create{namespace}Disk"})
    assert result.ok, result.error
    field = "vmName" if namespace == "vmm" else "clusterName"
    assert result.payload["request_body_schema"] == {field: {"type": "string", "enum": [namespace]}}


@pytest.mark.parametrize("tool", ["getOperationSchema", "getCodeSample", "getOperationPermissions"])
def test_ambiguous_discovery_requires_namespace_even_after_cache_is_warmed(dispatcher, tool):
    dispatcher.call_tool("getOperationSchema", {"operation": "getDiskById", "namespace": "vmm"})
    result = dispatcher.call_tool(tool, {"operation": "getDiskById", "language": "python"})
    assert not result.ok
    assert result.error["code"] == "ambiguous_operation"
    assert "clustermgmt" in result.error["detail"]
    assert "vmm" in result.error["detail"]


@pytest.mark.parametrize("namespace", ["clustermgmt", "vmm"])
def test_samples_and_permissions_follow_namespace(dispatcher, namespace):
    args = {"operation": "getDiskById", "namespace": namespace, "language": "python"}
    sample = dispatcher.call_tool("getCodeSample", args)
    assert sample.ok, sample.error
    assert sample.payload["source"] == f"print('{namespace}')"
    permissions = dispatcher.call_tool("getOperationPermissions", args)
    assert permissions.ok, permissions.error
    assert permissions.payload["namespace"] == namespace
    assert permissions.payload["permission_name"] == f"View {namespace} disk"


@pytest.mark.parametrize("tool", ["getOperationSchema", "getCodeSample", "getOperationPermissions"])
@pytest.mark.parametrize("namespace", ["unknown", "", 42, [], {}])
def test_invalid_or_unknown_namespace_never_falls_back(dispatcher, tool, namespace):
    result = dispatcher.call_tool(tool, {
        "operation": "getDiskById", "namespace": namespace, "language": "python",
    })
    assert not result.ok
    assert result.error["code"] == ("unknown_operation" if namespace == "unknown" else "invalid_arguments")


def test_discovery_tools_advertise_optional_namespace(dispatcher):
    for tool in dispatcher.list_tools():
        if tool["name"] in {"getOperationSchema", "getCodeSample", "getOperationPermissions"}:
            assert tool["inputSchema"]["properties"]["namespace"]["type"] == "string"
            assert "namespace" not in tool["inputSchema"]["required"]


def test_operation_index_retains_operations_with_the_same_name(dispatcher):
    index = dispatcher.load_result.operation_index
    assert len(index) == 4
    assert index["clustermgmt:getDiskById"]["namespace"] == "clustermgmt"
    assert index["vmm:getDiskById"]["namespace"] == "vmm"


@pytest.mark.parametrize("namespace", ["clustermgmt", "vmm"])
def test_discovery_and_execution_select_the_same_operation(dispatcher, namespace, monkeypatch):
    calls = []
    monkeypatch.setattr(dispatcher.api_handler, "execute_request", lambda **kwargs: calls.append(kwargs))
    schema = dispatcher.call_tool("getOperationSchema", {
        "operation": "getDiskById", "namespace": namespace,
    }).payload
    result = dispatcher.call_tool(f"{namespace}_execute", {
        "operation": "getDiskById", "extId": "disk", "vmExtId": "vm",
    })
    assert result.ok, result.error
    assert calls[0]["path"] == schema["path"]
    assert set(calls[0]["path_params"]) == {param["name"] for param in schema["path_parameters"]}
