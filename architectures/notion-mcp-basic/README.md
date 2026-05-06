# Notion MCP Basic Architecture

Securely connecting an AI interface to Notion's MCP server in an enterprise environment.

## Overview

This pattern covers the most common enterprise MCP use case: giving an AI assistant (Claude, an internal copilot, or a custom agent) secure access to a Notion workspace through MCP.

The naive approach is to just point the AI at the Notion MCP endpoint and hand it a token. In enterprise, that gets you a security review rejection. This template shows the layered approach that actually passes review.

## Architecture

```
+------------------+      +-------------------+      +------------------+
|                  |      |                   |      |                  |
|   AI Interface   +----->+   MCP Gateway     +----->+   Notion MCP     |
|   (Claude, etc)  |      |   (your proxy)    |      |   Server         |
|                  |      |                   |      |                  |
+------------------+      +--------+----------+      +------------------+
                                   |
                          +--------v----------+
                          |                   |
                          |   Auth + Scoping  |
                          |   Layer           |
                          |                   |
                          +--------+----------+
                                   |
                          +--------v----------+
                          |                   |
                          |   Audit Logger    |
                          |                   |
                          +-------------------+
```

## Why the Gateway Layer?

You do not point the AI directly at Notion's MCP server because:

1. **Token management.** The gateway holds and rotates the Notion API token. The AI interface never sees raw credentials.
2. **Permission scoping.** The gateway filters which Notion pages, databases, and operations the AI can access. Even if the token has broad access, the gateway enforces least privilege.
3. **Audit logging.** Every request the AI makes to Notion gets logged with context (who triggered it, what was accessed, timestamps).
4. **Rate limiting.** The gateway throttles requests to prevent the AI from hammering the Notion API during agentic loops.
5. **Data residency.** The gateway can enforce that certain data types never leave specific regions.

## Setup

### Prerequisites

- Docker and Docker Compose installed
- A Notion integration token with access to the target workspace
- Your AI interface configured to point at MCP endpoints

### Environment Variables

Create a `.env` file:

```env
NOTION_API_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxxxxxx
ALLOWED_PAGE_IDS=page_id_1,page_id_2
ALLOWED_OPERATIONS=read,search
LOG_LEVEL=info
RATE_LIMIT_PER_MINUTE=30
MCP_GATEWAY_PORT=8080
```

### Run

```bash
docker-compose up -d
```

Point your AI interface to `http://localhost:8080/mcp` as the MCP endpoint.

## Configuration

### Scoping Access

Edit the `ALLOWED_PAGE_IDS` variable to control which Notion pages the AI can access. Leave empty to allow all pages the token has access to (not recommended for production).

`ALLOWED_OPERATIONS` controls what the AI can do:

- `read` - Read page content and database entries
- `search` - Search across the workspace
- `write` - Create and update pages (enable with caution)
- `delete` - Delete pages (almost never enable this)

### Rate Limiting

`RATE_LIMIT_PER_MINUTE` defaults to 30. For agentic workflows that make rapid sequential calls, you may need to increase this. For simple Q&A use cases, 10 to 15 is sufficient.

## Production Checklist

Before deploying this pattern to production:

- [ ] Notion token is stored in a secrets manager (not in .env files)
- [ ] ALLOWED_PAGE_IDS is explicitly set (no wildcard access)
- [ ] ALLOWED_OPERATIONS is restricted to what the AI actually needs
- [ ] Audit logs are being shipped to your logging infrastructure
- [ ] Rate limits are tested under realistic agentic load
- [ ] Data residency review completed (see /security/data-residency-checklist.md)
- [ ] Gateway is running behind your existing API gateway / load balancer
- [ ] TLS is enabled for all connections
