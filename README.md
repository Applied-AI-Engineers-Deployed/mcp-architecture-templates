# MCP Architecture Templates

Production-grade Model Context Protocol (MCP) architecture templates built for enterprise deployments.

These are not toy wrappers or demo apps. These are sanitized patterns pulled from real enterprise AI deployments where data residency, permission scoping, and security reviews are non-negotiable.

## What is MCP in an Enterprise Context?

MCP is the protocol layer that lets AI interfaces (Claude, internal copilots, custom agents) connect to external systems securely. In enterprise, this means connecting to internal tools, databases, SaaS products, and custom APIs while respecting corporate security policies.

The gap most engineers hit: MCP tutorials show you how to connect a local model to a single tool. Enterprise requires multi-tenant permission scoping, data residency compliance, audit logging, and graceful failure handling across dozens of integrations. That is what this repo covers.

## What is in this repo

```
architectures/
  notion-mcp-basic/       # Connecting AI to Notion's MCP server securely
  custom-internal-mcp/    # Building your own MCP server with permission scoping

security/
  data-residency-checklist.md      # Pre-deployment checklist for data residency
  permission-scoping-patterns.md   # Patterns for scoping MCP permissions correctly
```

## Stack

- **Python** for MCP server implementations
- **TypeScript** for client-side integrations
- **Docker** for containerized deployments

## How to Use These Templates

1. Pick the architecture pattern closest to your use case
2. Read the architecture-level README first (it covers the "why" before the "how")
3. Adapt the code to your environment, auth provider, and compliance requirements
4. Run through the security checklists before deploying to production

These are starting points, not copy-paste solutions. Every enterprise environment has its own constraints. The patterns here are designed to be adapted, not deployed blindly.

## Security Considerations

Every template in this repo is built with these assumptions:

- **Zero trust by default.** Every request is authenticated and scoped. No implicit trust between services.
- **Least privilege.** MCP servers expose only the operations the AI interface actually needs. Nothing more.
- **Audit everything.** Every tool call, every data access, every permission check gets logged.
- **Data stays where it belongs.** Templates include data residency checkpoints so you are not accidentally routing sensitive data through regions that violate your compliance requirements.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

## License

MIT
