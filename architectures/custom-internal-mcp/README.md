# Custom Internal MCP Server

Building and deploying a custom MCP server with permission scoping for internal enterprise tools.

## When You Need This

Notion, Slack, GitHub all have their own MCP servers. But most enterprise AI deployments eventually hit a tool that does not have a public MCP server: an internal CRM, a proprietary data pipeline, a legacy system with a REST API from 2014.

This template gives you a production-ready pattern for wrapping any internal system in an MCP server with permission scoping built in from the start.

## Architecture

```
+------------------+      +-------------------+      +------------------+
|                  |      |                   |      |                  |
|   AI Interface   +----->+   Custom MCP      +----->+   Internal       |
|                  |      |   Server (Python) |      |   System API     |
|                  |      |                   |      |                  |
+------------------+      +--------+----------+      +------------------+
                                   |
                          +--------v----------+
                          |  Permission       |
                          |  Scoping Layer    |
                          |                   |
                          |  - Role checking  |
                          |  - Resource ACLs  |
                          |  - Op filtering   |
                          +--------+----------+
                                   |
                          +--------v----------+
                          |  Audit + Rate     |
                          |  Limiting         |
                          +-------------------+
```

## Key Design Decisions

### Permission scoping is not optional

The server.py template includes a `PermissionScope` class that enforces:

- **Role-based access.** Different users/AI interfaces get different tool access levels.
- **Resource-level ACLs.** Even within an allowed operation, you can restrict which specific resources (IDs, tables, endpoints) are accessible.
- **Operation filtering.** Read vs write vs delete are independently controllable per role.

This is not over-engineering. It is the difference between passing and failing a security review.

### Every tool call is audited

The `AuditLogger` in server.py logs every tool invocation with:

- Timestamp
- Caller identity
- Tool name and parameters
- Result status (success/failure)
- Execution duration

Ship these logs to your existing logging infrastructure. When the security team asks "what did the AI access last Tuesday," you need an answer.

### Rate limiting is per-caller

Rate limits are applied per authenticated caller, not globally. This prevents one runaway agentic loop from starving other consumers of the MCP server.

## Files

- `server.py` - The MCP server implementation in Python with permission scoping
- `client.ts` - TypeScript client for connecting to the server with auth handling

## Setup

### Server

```bash
pip install mcp pydantic uvicorn
python server.py
```

The server starts on port 8080 by default. Set the `MCP_PORT` environment variable to change it.

### Client

```bash
npm install
npx ts-node client.ts
```

## Adapting to Your Internal System

1. Replace the example tools in `server.py` with tools that call your internal API
2. Define your permission scopes in the `ROLE_PERMISSIONS` config
3. Update the auth handler to integrate with your identity provider (Okta, Azure AD, etc.)
4. Configure the audit logger to ship to your logging stack
5. Run through the security checklist before deploying

## Production Checklist

- [ ] Auth handler integrated with your corporate identity provider
- [ ] Permission scopes defined for every role that will access the server
- [ ] Audit logs shipping to centralized logging
- [ ] Rate limits tested under realistic agentic load
- [ ] TLS enabled
- [ ] Server running behind corporate API gateway
- [ ] Health check endpoint monitored
- [ ] Secrets stored in a secrets manager (not in environment variables or config files)
