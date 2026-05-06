"""
Custom Internal MCP Server
Production-grade MCP server with permission scoping, audit logging,
and rate limiting for enterprise deployments.

Adapt the tools, permissions, and auth handler to your internal systems.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from mcp.server import Server
from mcp.types import Tool, TextContent
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp-server")


# ---------------------------------------------------------------------------
# Permission Scoping
# ---------------------------------------------------------------------------

class Operation(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SEARCH = "search"


@dataclass
class PermissionScope:
    """Defines what a specific role can access."""
    allowed_tools: list[str]
    allowed_operations: list[Operation]
    allowed_resource_ids: list[str] | None = None  # None = all resources
    max_results: int = 50


# Define your roles and their permission scopes here.
# Adapt these to match your org's access control model.
ROLE_PERMISSIONS: dict[str, PermissionScope] = {
    "ai-assistant-readonly": PermissionScope(
        allowed_tools=["get_record", "search_records", "get_schema"],
        allowed_operations=[Operation.READ, Operation.SEARCH],
        max_results=25,
    ),
    "ai-assistant-readwrite": PermissionScope(
        allowed_tools=[
            "get_record", "search_records", "get_schema",
            "create_record", "update_record",
        ],
        allowed_operations=[Operation.READ, Operation.SEARCH, Operation.WRITE],
        max_results=50,
    ),
    "ai-assistant-admin": PermissionScope(
        allowed_tools=[
            "get_record", "search_records", "get_schema",
            "create_record", "update_record", "delete_record",
        ],
        allowed_operations=[
            Operation.READ, Operation.SEARCH,
            Operation.WRITE, Operation.DELETE,
        ],
        max_results=100,
    ),
}


def check_permission(role: str, tool_name: str, operation: Operation) -> bool:
    """Check if a role has permission to use a tool with a given operation."""
    scope = ROLE_PERMISSIONS.get(role)
    if scope is None:
        logger.warning(f"Unknown role attempted access: {role}")
        return False
    if tool_name not in scope.allowed_tools:
        logger.warning(f"Role '{role}' denied access to tool '{tool_name}'")
        return False
    if operation not in scope.allowed_operations:
        logger.warning(
            f"Role '{role}' denied operation '{operation.value}' on '{tool_name}'"
        )
        return False
    return True


def check_resource_access(role: str, resource_id: str) -> bool:
    """Check if a role can access a specific resource ID."""
    scope = ROLE_PERMISSIONS.get(role)
    if scope is None:
        return False
    # None means all resources are accessible
    if scope.allowed_resource_ids is None:
        return True
    return resource_id in scope.allowed_resource_ids


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    timestamp: str
    caller_id: str
    caller_role: str
    tool_name: str
    parameters: dict[str, Any]
    status: str  # "success", "denied", "error"
    duration_ms: float | None = None
    error_message: str | None = None


class AuditLogger:
    """
    Structured audit logger for MCP tool calls.

    In production, replace the file-based approach with your
    logging infrastructure (Datadog, Splunk, CloudWatch, etc.)
    """

    def __init__(self, log_path: str = "/var/log/mcp-server/audit.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        record = {
            "timestamp": entry.timestamp,
            "caller_id": entry.caller_id,
            "caller_role": entry.caller_role,
            "tool": entry.tool_name,
            "params": entry.parameters,
            "status": entry.status,
            "duration_ms": entry.duration_ms,
            "error": entry.error_message,
        }
        logger.info(f"AUDIT: {json.dumps(record)}")
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            logger.error(f"Failed to write audit log: {e}")


audit = AuditLogger()


# ---------------------------------------------------------------------------
# Rate Limiting (per caller)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple sliding window rate limiter per caller."""

    def __init__(self, max_per_minute: int = RATE_LIMIT_PER_MINUTE):
        self.max_per_minute = max_per_minute
        self.windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, caller_id: str) -> bool:
        now = time.time()
        window = self.windows[caller_id]
        # Remove entries older than 60 seconds
        self.windows[caller_id] = [t for t in window if now - t < 60]
        if len(self.windows[caller_id]) >= self.max_per_minute:
            return False
        self.windows[caller_id].append(now)
        return True


rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Auth Handler (adapt to your identity provider)
# ---------------------------------------------------------------------------

@dataclass
class CallerIdentity:
    caller_id: str
    role: str


def authenticate_request(headers: dict[str, str]) -> CallerIdentity | None:
    """
    Extract and validate caller identity from request headers.

    REPLACE THIS with your actual auth logic:
    - Validate JWT from Okta/Azure AD/Auth0
    - Extract role from token claims
    - Map to your ROLE_PERMISSIONS keys

    This stub uses a simple bearer token for demonstration.
    """
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.removeprefix("Bearer ")

    # STUB: Replace with real token validation
    # In production this would decode a JWT, validate signature,
    # check expiry, and extract claims
    DEMO_TOKENS = {
        "readonly-token": CallerIdentity("ai-copilot-1", "ai-assistant-readonly"),
        "readwrite-token": CallerIdentity("ai-copilot-2", "ai-assistant-readwrite"),
    }

    return DEMO_TOKENS.get(token)


# ---------------------------------------------------------------------------
# Internal System Client (adapt to your API)
# ---------------------------------------------------------------------------

class InternalSystemClient:
    """
    Client for your internal system API.

    Replace the methods below with actual calls to your internal
    REST API, gRPC service, database, or whatever you are wrapping.
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv("INTERNAL_API_URL", "http://localhost:9000")

    async def get_record(self, record_id: str) -> dict:
        """Fetch a single record by ID."""
        # REPLACE: Call your actual internal API
        return {
            "id": record_id,
            "status": "active",
            "data": {"placeholder": "Replace with real API call"},
        }

    async def search_records(self, query: str, max_results: int = 25) -> list[dict]:
        """Search records."""
        # REPLACE: Call your actual search endpoint
        return [
            {"id": "result-1", "score": 0.95, "summary": "Placeholder result"},
        ]

    async def create_record(self, data: dict) -> dict:
        """Create a new record."""
        # REPLACE: Call your actual create endpoint
        return {"id": "new-record-id", "status": "created"}

    async def update_record(self, record_id: str, data: dict) -> dict:
        """Update an existing record."""
        # REPLACE: Call your actual update endpoint
        return {"id": record_id, "status": "updated"}

    async def delete_record(self, record_id: str) -> dict:
        """Delete a record."""
        # REPLACE: Call your actual delete endpoint
        return {"id": record_id, "status": "deleted"}

    async def get_schema(self) -> dict:
        """Get the schema of available records/fields."""
        # REPLACE: Return your actual schema
        return {
            "fields": ["id", "name", "status", "created_at", "updated_at"],
            "types": {"id": "string", "name": "string", "status": "enum"},
        }


system_client = InternalSystemClient()


# ---------------------------------------------------------------------------
# MCP Server Definition
# ---------------------------------------------------------------------------

server = Server("custom-internal-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return [
        Tool(
            name="get_record",
            description="Fetch a single record by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "The unique identifier of the record",
                    }
                },
                "required": ["record_id"],
            },
        ),
        Tool(
            name="search_records",
            description="Search for records matching a query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 25,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_schema",
            description="Get the schema of available record fields",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="create_record",
            description="Create a new record",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Record data to create",
                    }
                },
                "required": ["data"],
            },
        ),
        Tool(
            name="update_record",
            description="Update an existing record",
            inputSchema={
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "ID of the record to update",
                    },
                    "data": {
                        "type": "object",
                        "description": "Updated record data",
                    },
                },
                "required": ["record_id", "data"],
            },
        ),
        Tool(
            name="delete_record",
            description="Delete a record by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "ID of the record to delete",
                    }
                },
                "required": ["record_id"],
            },
        ),
    ]


# Map tool names to their operation type
TOOL_OPERATIONS: dict[str, Operation] = {
    "get_record": Operation.READ,
    "search_records": Operation.SEARCH,
    "get_schema": Operation.READ,
    "create_record": Operation.WRITE,
    "update_record": Operation.WRITE,
    "delete_record": Operation.DELETE,
}


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with permission checking, rate limiting, and audit logging."""

    # In production, extract these from the request context
    # This stub uses defaults for demonstration
    caller = CallerIdentity("demo-caller", "ai-assistant-readonly")

    start_time = time.time()
    operation = TOOL_OPERATIONS.get(name, Operation.READ)

    # Rate limit check
    if not rate_limiter.is_allowed(caller.caller_id):
        audit.log(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            caller_id=caller.caller_id,
            caller_role=caller.role,
            tool_name=name,
            parameters=arguments,
            status="rate_limited",
        ))
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Rate limit exceeded. Try again shortly."}),
        )]

    # Permission check
    if not check_permission(caller.role, name, operation):
        audit.log(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            caller_id=caller.caller_id,
            caller_role=caller.role,
            tool_name=name,
            parameters=arguments,
            status="denied",
        ))
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Permission denied for tool '{name}'"}),
        )]

    # Resource-level access check (for tools that operate on specific records)
    resource_id = arguments.get("record_id")
    if resource_id and not check_resource_access(caller.role, resource_id):
        audit.log(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            caller_id=caller.caller_id,
            caller_role=caller.role,
            tool_name=name,
            parameters=arguments,
            status="denied",
            error_message=f"No access to resource {resource_id}",
        ))
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Access denied for resource '{resource_id}'"}),
        )]

    # Execute the tool
    try:
        result = await _execute_tool(name, arguments, caller.role)
        duration_ms = (time.time() - start_time) * 1000

        audit.log(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            caller_id=caller.caller_id,
            caller_role=caller.role,
            tool_name=name,
            parameters=arguments,
            status="success",
            duration_ms=round(duration_ms, 2),
        ))

        return [TextContent(type="text", text=json.dumps(result))]

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        audit.log(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            caller_id=caller.caller_id,
            caller_role=caller.role,
            tool_name=name,
            parameters=arguments,
            status="error",
            duration_ms=round(duration_ms, 2),
            error_message=str(e),
        ))
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Internal error: {str(e)}"}),
        )]


async def _execute_tool(name: str, args: dict, role: str) -> dict:
    """Route tool calls to the internal system client."""
    scope = ROLE_PERMISSIONS.get(role)
    max_results = scope.max_results if scope else 25

    if name == "get_record":
        return await system_client.get_record(args["record_id"])
    elif name == "search_records":
        limit = min(args.get("max_results", max_results), max_results)
        return {"results": await system_client.search_records(args["query"], limit)}
    elif name == "get_schema":
        return await system_client.get_schema()
    elif name == "create_record":
        return await system_client.create_record(args["data"])
    elif name == "update_record":
        return await system_client.update_record(args["record_id"], args["data"])
    elif name == "delete_record":
        return await system_client.delete_record(args["record_id"])
    else:
        raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server

    async def main():
        logger.info(f"Starting Custom Internal MCP Server on stdio")
        logger.info(f"Rate limit: {RATE_LIMIT_PER_MINUTE}/min per caller")
        logger.info(f"Roles configured: {list(ROLE_PERMISSIONS.keys())}")

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)

    asyncio.run(main())
