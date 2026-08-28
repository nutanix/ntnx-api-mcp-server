"""MCP stdio runtime server entrypoint."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import types
from mcp.server import NotificationOptions
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

import importlib.metadata

from src.config import Settings
from src.server import build_runtime_dispatcher


def _to_mcp_tool(definition: dict[str, Any]) -> types.Tool:
    """Convert internal tool definition to MCP SDK Tool model."""
    raw_annotations = definition.get("annotations")
    annotations = types.ToolAnnotations(**raw_annotations) if raw_annotations else None
    return types.Tool(
        name=definition["name"],
        description=definition.get("description"),
        inputSchema=definition.get("inputSchema", {"type": "object", "properties": {}}),
        annotations=annotations,
        _meta=definition.get("metadata"),
    )


def _build_instructions(namespaces: list[str]) -> str:
    """Build the MCP instructions field dynamically from loaded namespaces."""
    ns_routing = ", ".join(f'"{ns}" -> {ns}_execute' for ns in sorted(namespaces))

    return (
        "NUTANIX V4 API MCP SERVER - DISCOVERY PROTOCOL\n\n"
        "NORMAL PATH (always follow this sequence):\n"
        "1. Call listOperations(search='<1-2 keyword tokens>') - returns ranked results.\n"
        "2. Position 1 is the server's highest-confidence match.\n"
        "3. Check relevance_score and match_fields:\n"
        "   - match_fields containing 'operation_id' = strong match, proceed with confidence.\n"
        "   - match_fields containing only 'search_text' = weak match, try a different keyword.\n"
        "4. Call getOperationSchema(operation='<operation>') to confirm parameters.\n"
        "5. For POST / PUT / PATCH operations, ALSO call getCodeSample(operation='<operation>')\n"
        "   BEFORE executing. The code sample shows the minimal valid payload structure and\n"
        "   field constraints not visible in the schema (e.g. server-assigned fields that must\n"
        "   be omitted even if schema lists them).\n"
        "   POST rule: only send fields you explicitly intend to set. Do NOT speculatively\n"
        "   include fields from the schema that the user did not ask for — server-assigned\n"
        "   fields must be omitted even when their values appear schema-valid.\n"
        "6. Call {namespace}_execute(operation='<operation>', ...) using the EXACT\n"
        "   namespace and operation values from the listOperations result.\n\n"
        "VARIANT OPERATIONS:\n"
        "Some operations exist in multiple path variants (e.g. AHV vs ESXi hypervisors).\n"
        "These are registered as '{discriminator}_{operationId}', e.g. 'ahv_listVms' and\n"
        "'esxi_listVms'. Each is a distinct, fully-addressable operation.\n"
        "- When path_variant is present in a listOperations result, that IS the operation to call.\n"
        "- spec_operation_id shows the original Nutanix spec name for reference only.\n"
        "- Default rule: prefer 'ahv_' variants for VMM operations when the cluster\n"
        "  hypervisor is not specified by the user.\n\n"
        "NAMESPACE ROUTING - GUARANTEED CONTRACT:\n"
        "The 'namespace' field in every listOperations result is the EXACT prefix of the\n"
        "correct execute tool. Use the tool as it appears in your available tools list —\n"
        "do NOT construct tool names manually. The pattern is '{namespace}_execute' but\n"
        "the actual callable name may include a server prefix added by your MCP client.\n"
        "Always select from your available tools list, never hardcode a tool name string.\n"
        f"Loaded namespaces: {ns_routing}\n\n"
        "PUT / PATCH WORKFLOW (If-Match required):\n"
        "Operations that list 'If-Match' in header_parameters require an ETag.\n"
        "1. Always call the corresponding GET operation first (same resource path).\n"
        "2. Extract the '_etag' field AND the full resource body from the GET response.\n"
        "3. Use the full GET body as the base for your PUT/PATCH request_body:\n"
        "   a. Copy the entire GET response body.\n"
        "   b. Remove '_etag' (goes as If-Match header, not body) and 'links' (HATEOAS,\n"
        "      server rejects if echoed in PUT body).\n"
        "   c. Cross-check field names against getOperationSchema. If schema marks a field\n"
        "      as deprecated: true, omit it from the PUT body entirely. Do not attempt to\n"
        "      find a replacement — send the body without it and let the server validate.\n"
        "   d. Modify only the specific fields the user asked to change. Send ALL others\n"
        "      unchanged — including every field listed in immutable_fields. Omitting any\n"
        "      field the server expects causes a validation error and wastes an ETag.\n"
        "4. Pass '_etag' as 'If-Match' flat key in the PUT/PATCH call.\n"
        "Note: 'NTNX-Request-Id' is auto-injected by the server for every call; no action needed.\n\n"
        "SCHEMA CALL RULE:\n"
        "Call getOperationSchema before ANY operation where parameter names, formats, or valid\n"
        "values cannot be directly inferred from user intent —\n"
        "not just writes. Path param names (e.g. 'clusterExtId' not 'clusterId'), query\n"
        "param constraints (max/min values), and body shape all come from this call.\n"
        "Never assume param names; always verify from schema output.\n\n"
        "DEFINITIVE ERROR RULE:\n"
        "Errors that confirm resource state require no verification call:\n"
        "  - *_NOT_FOUND / 404 → resource absent. Do not call GET or listX to confirm.\n"
        "  - ALREADY_POWERED_ON / ALREADY_POWERED_OFF → action redundant, inform user.\n"
        "  - Any error with 'already in desired state' wording → stop, inform user.\n"
        "One error response is sufficient to determine the situation.\n\n"
        "ACTION OPERATIONS RULE:\n"
        "State-toggle operations (powerOn, powerOff, reboot, shutdown, suspend, resume,\n"
        "failover, and similar action verbs) do NOT require a preflight GET to check\n"
        "current state. Call them directly. If the resource is already in the desired\n"
        "state, the API returns a graceful error — handle it with DEFINITIVE ERROR RULE.\n"
        "Exception: before attachment operations on a parent resource, verify the parent\n"
        "is in an active/ready state via a GET call first.\n\n"
        "ODATA FILTER / SELECT RULE:\n"
        "getOperationSchema exposes an 'odata_fields' list on $filter, $select, $orderby,\n"
        "and $expand parameters when available. These are the ONLY valid field names for\n"
        "that parameter on that operation — use them verbatim, never guess or invent names.\n"
        "If 'odata_fields' is absent for a param, omit that param entirely on the first call;\n"
        "inspect the response fields, then add the param on retry using real field names.\n"
        "If a filtered call returns a server error (5xx or OData error code), the field\n"
        "is NOT filterable server-side. Do NOT retry with the same or similar filter.\n"
        "Immediately fall back to an unfiltered fetch and apply filtering client-side.\n"
        "Also check query_parameters in getOperationSchema for $limit maximum before\n"
        "sending pagination params — never exceed the documented max.\n\n"
        "NESTED COMPLEX FIELDS RULE:\n"
        "For array fields whose items are oneOf (e.g. nics, disks, gpus on a VM), do NOT\n"
        "attempt to populate them inline during the parent resource creation. Instead:\n"
        "1. Create the parent resource with bare required fields only.\n"
        "2. Use the dedicated child create operation (createNic, createDisk, createGpu)\n"
        "   for each nested item after the parent exists.\n"
        "When a oneOf field is required, read the 'when' discriminator value from the\n"
        "schema variants — use it verbatim as the $objectType value. Never guess.\n\n"
        "ZERO RESULTS PATH:\n"
        "If listOperations returns empty, your keyword uses vocabulary not in the spec.\n"
        "Retry once using abbreviated API-style terms (e.g. 'vm' not 'virtual machine',\n"
        "'dataprotection' not 'backup', 'clustermgmt' not 'cluster management').\n\n"
        "NEVER-GUESS RULE:\n"
        "Calling any {namespace}_execute with an operation not returned by listOperations\n"
        "will return unknown_operation. Always discover first."
    )


def build_mcp_server(settings: Settings) -> Server:
    """Build the MCP server and register Nutanix runtime tools."""
    try:
        _version = importlib.metadata.version("ntnx-api-mcp-server")
    except importlib.metadata.PackageNotFoundError:
        _version = "dev"

    dispatcher = build_runtime_dispatcher(settings)

    # Derive loaded namespaces for the dynamic instructions field.
    loaded_namespaces = sorted({op.namespace for op in dispatcher.generator.operations})
    server = Server(
        name="nutanix-v4-mcp-server",
        version=_version,
        instructions=_build_instructions(loaded_namespaces),
    )

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [_to_mcp_tool(tool) for tool in dispatcher.list_tools()]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult | dict[str, Any]:
        result = dispatcher.call_tool(name, arguments)
        if result.ok:
            return result.as_dict()
        return types.CallToolResult(
            isError=True,
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(result.as_dict(), indent=2),
                )
            ],
            structuredContent=result.as_dict(),
        )

    return server


async def _serve_stdio(settings: Settings) -> None:
    server = build_mcp_server(settings)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )


def serve_stdio(settings: Settings) -> None:
    """Run the MCP stdio server until terminated."""
    asyncio.run(_serve_stdio(settings))
