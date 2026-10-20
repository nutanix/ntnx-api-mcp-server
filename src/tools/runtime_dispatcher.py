"""Runtime dispatch for namespace execution and discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Protocol

from src.config import Settings
from src.generators import ToolContractError, ToolGenerator
from src.handlers import APIHandler
from src.parsers import OperationInfo


ODATA_ALIAS_MAP = {
    "_page": "$page",
    "_limit": "$limit",
    "_filter": "$filter",
    "_orderby": "$orderby",
    "_select": "$select",
    "_expand": "$expand",
}

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolDispatchResult:
    """Response returned by tool dispatch operations."""

    ok: bool
    tool: str
    payload: Any = None
    error: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "payload": self.payload,
            "error": self.error,
        }


class RuntimeLoadResult(Protocol):
    """Structural type for startup-loaded runtime data."""

    operations: list[OperationInfo]
    namespace_tools: list[dict[str, Any]]
    discovery_tools: list[dict[str, Any]]
    generator: ToolGenerator


class RuntimeToolDispatcher:
    """Dispatch runtime tool calls using loaded operations."""

    def __init__(self, settings: Settings, load_result: RuntimeLoadResult) -> None:
        self.settings = settings
        self.load_result = load_result
        self.generator = load_result.generator
        self.api_handler = APIHandler(settings)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return namespace and progressive discovery tools."""
        return [*self.load_result.namespace_tools, *self.load_result.discovery_tools]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolDispatchResult:
        """Dispatch a single tool call."""
        args = dict(arguments or {})
        match name:
            case "listOperations":
                result = self._handle_list_operations(args)
            case "getOperationSchema":
                result = self._handle_get_operation_schema(args)
            case "getCodeSample":
                result = self._handle_get_code_sample(args)
            case "getOperationPermissions":
                result = self._handle_get_operation_permissions(args)
            case _ if name.endswith("_execute"):
                namespace = name[: -len("_execute")]
                result = self._handle_namespace_execute(namespace, args)
            case _:
                result = ToolDispatchResult(
                    ok=False,
                    tool=name,
                    error={"code": "unknown_tool", "detail": f"Tool '{name}' is not registered."},
                )

        LOGGER.info(
            "event=tool_call_dispatched tool=%s ok=%s error_code=%s",
            name,
            result.ok,
            (result.error or {}).get("code"),
        )
        return result

    def _handle_list_operations(self, args: dict[str, Any]) -> ToolDispatchResult:
        limit = int(args.get("limit", 20))
        offset = int(args.get("offset", 0))
        items = self.generator.list_operations(
            namespace=args.get("namespace"),
            search=args.get("search"),
            limit=limit,
            offset=offset,
        )
        return ToolDispatchResult(ok=True, tool="listOperations", payload=items)

    def _handle_get_operation_schema(self, args: dict[str, Any]) -> ToolDispatchResult:
        operation = args.get("operation")
        if not isinstance(operation, str) or not operation:
            return ToolDispatchResult(
                ok=False,
                tool="getOperationSchema",
                error={"code": "invalid_arguments", "detail": "'operation' is required."},
            )
        try:
            schema = self.generator.get_operation_schema(operation, namespace=args.get("namespace"))
        except ToolContractError as exc:
            return ToolDispatchResult(ok=False, tool="getOperationSchema", error=exc.as_dict())
        except KeyError:
            return ToolDispatchResult(
                ok=False,
                tool="getOperationSchema",
                error={"code": "unknown_operation", "detail": f"Unknown operation '{operation}'."},
            )
        return ToolDispatchResult(ok=True, tool="getOperationSchema", payload=schema)

    def _handle_get_code_sample(self, args: dict[str, Any]) -> ToolDispatchResult:
        operation = args.get("operation")
        language = args.get("language")
        if not isinstance(operation, str) or not isinstance(language, str) or not operation or not language:
            return ToolDispatchResult(
                ok=False,
                tool="getCodeSample",
                error={"code": "invalid_arguments", "detail": "'operation' and 'language' are required."},
            )
        try:
            sample = self.generator.get_code_sample(operation, language, namespace=args.get("namespace"))
        except ToolContractError as exc:
            return ToolDispatchResult(ok=False, tool="getCodeSample", error=exc.as_dict())
        except KeyError:
            return ToolDispatchResult(
                ok=False,
                tool="getCodeSample",
                error={"code": "unknown_operation", "detail": f"Unknown operation '{operation}'."},
            )
        if sample is None:
            return ToolDispatchResult(
                ok=False,
                tool="getCodeSample",
                error={
                    "code": "missing_code_sample",
                    "detail": f"No code sample available for '{operation}' in '{language}'.",
                },
            )
        return ToolDispatchResult(ok=True, tool="getCodeSample", payload=sample)

    def _handle_get_operation_permissions(self, args: dict[str, Any]) -> ToolDispatchResult:
        operation = args.get("operation")
        if not isinstance(operation, str) or not operation:
            return ToolDispatchResult(
                ok=False,
                tool="getOperationPermissions",
                error={"code": "invalid_arguments", "detail": "'operation' is required."},
            )
        try:
            permissions = self.generator.get_operation_permissions(operation, namespace=args.get("namespace"))
        except ToolContractError as exc:
            return ToolDispatchResult(ok=False, tool="getOperationPermissions", error=exc.as_dict())
        except KeyError:
            return ToolDispatchResult(
                ok=False,
                tool="getOperationPermissions",
                error={"code": "unknown_operation", "detail": f"Unknown operation '{operation}'."},
            )
        return ToolDispatchResult(ok=True, tool="getOperationPermissions", payload=permissions)

    def _handle_namespace_execute(self, namespace: str, args: dict[str, Any]) -> ToolDispatchResult:
        operation_id = args.get("operation")
        if not isinstance(operation_id, str) or not operation_id:
            return ToolDispatchResult(
                ok=False,
                tool=f"{namespace}_execute",
                error={"code": "invalid_arguments", "detail": "'operation' is required."},
            )

        try:
            self.generator.validate_namespace_operation_request(namespace, operation_id, args)
        except ToolContractError as exc:
            return ToolDispatchResult(
                ok=False,
                tool=f"{namespace}_execute",
                error=exc.as_dict(),
            )

        operation = self._find_operation(namespace, operation_id)
        if operation is None:
            return ToolDispatchResult(
                ok=False,
                tool=f"{namespace}_execute",
                error={"code": "unknown_operation", "detail": f"Unknown operation '{operation_id}'."},
            )

        if self.settings.read_only_mode and operation.method.upper() != "GET":
            return ToolDispatchResult(
                ok=False,
                tool=f"{namespace}_execute",
                error={
                    "code": "read_only_mode",
                    "detail": (
                        f"Server is in read-only mode. Operation '{operation_id}' "
                        f"({operation.method.upper()}) is not permitted."
                    ),
                },
            )

        path_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}
        headers: dict[str, Any] = {}

        for parameter in operation.parameters:
            param_name = parameter.name
            if param_name in args:
                value = args[param_name]
            else:
                value = args.get(self._get_alias_for_parameter(param_name))

            if value is None:
                continue
            if parameter.location == "path":
                path_params[param_name] = value
            elif parameter.location == "query":
                query_params[param_name] = value
            elif parameter.location == "header":
                headers[param_name] = value

        request_body = args.get("request_body")
        if request_body is not None and not isinstance(request_body, dict):
            return ToolDispatchResult(
                ok=False,
                tool=f"{namespace}_execute",
                error={"code": "invalid_arguments", "detail": "'request_body' must be an object."},
            )

        try:
            payload = self.api_handler.execute_request(
                method=operation.method,
                path=operation.path,
                path_params=path_params,
                query_params=query_params,
                headers=headers,
                body=request_body,
            )
        except Exception as exc:
            return ToolDispatchResult(
                ok=False,
                tool=f"{namespace}_execute",
                error={"code": "execution_error", "detail": str(exc)},
            )

        return ToolDispatchResult(ok=True, tool=f"{namespace}_execute", payload=payload)

    def _find_operation(self, namespace: str, operation_id: str) -> OperationInfo | None:
        for operation in self.load_result.operations:
            if operation.namespace == namespace and operation.registered_name == operation_id:
                return operation
        return None

    @staticmethod
    def _get_alias_for_parameter(param_name: str) -> str | None:
        for alias, original in ODATA_ALIAS_MAP.items():
            if original == param_name:
                return alias
        return None
