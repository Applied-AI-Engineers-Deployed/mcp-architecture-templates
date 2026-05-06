# Permission Scoping Patterns for MCP Deployments

How to scope MCP permissions correctly in enterprise. These are patterns, not opinions. Every one of these has been learned through a failed security review or a production incident.

## Pattern 1: Least Privilege by Default

**The rule:** An MCP server should expose exactly the tools the AI needs to do its job. Nothing more.

**The mistake:** Exposing all available tools and relying on the AI to "only use what it needs." LLMs are not access control systems. They will use tools they have access to if the context suggests it.

**Implementation:**

```
# BAD: Expose everything
tools = [get, search, create, update, delete, admin_reset, export_all]

# GOOD: Expose only what this use case needs
tools = [get, search]
```

Define tool sets per use case, not per server. If you have three different AI interfaces connecting to the same internal system, each one gets its own scoped tool set.

## Pattern 2: Role-Based Tool Access

**The pattern:** Map your existing RBAC model to MCP tool access.

```
Roles:
  ai-assistant-readonly:
    tools: [get_record, search_records, get_schema]
    operations: [read, search]

  ai-assistant-readwrite:
    tools: [get_record, search_records, create_record, update_record]
    operations: [read, search, write]

  ai-assistant-admin:
    tools: [all]
    operations: [all]
    # This role should almost never be used in production
```

**Key principle:** The AI's role should mirror the human user's role whose context it is operating in. If a user can only read records, the AI working on that user's behalf should also only be able to read records.

## Pattern 3: Resource-Level ACLs

Role-based access controls which tools you can use. Resource-level ACLs control which specific records, databases, or entities you can touch with those tools.

**Example:** An AI assistant has `get_record` access but should only be able to access records in the "Engineering" department, not "Legal" or "HR."

```python
RESOURCE_ACLS = {
    "ai-assistant-eng": {
        "allowed_departments": ["engineering", "product"],
        "denied_record_prefixes": ["HR-", "LEGAL-", "FINANCE-"],
    }
}
```

This is not optional in enterprise. Without resource-level ACLs, a read-only assistant with access to `search_records` can surface confidential HR documents to the wrong person.

## Pattern 4: Operation Segregation

Separate read operations from write operations at the infrastructure level, not just the permission level.

**Why:** If the AI can both read and write to the same system through the same MCP server, a prompt injection or malformed agent loop can cause data corruption.

**Implementation options:**

1. **Separate MCP servers:** One for read operations, one for write operations. Write server requires additional confirmation steps.
2. **Write confirmation layer:** Write operations go through a human-in-the-loop confirmation step before executing.
3. **Write-ahead log:** All write operations are logged to a separate audit trail before execution, with a configurable delay for rollback.

## Pattern 5: Temporal Scoping

Limit when the AI can access certain tools.

**Use cases:**
- Financial data tools are only accessible during business hours
- Deployment tools are locked during change freeze windows
- High-sensitivity tools require a time-bound access grant (similar to AWS STS temporary credentials)

```python
TEMPORAL_SCOPES = {
    "financial_tools": {
        "allowed_hours": (9, 17),  # 9 AM to 5 PM
        "allowed_days": [0, 1, 2, 3, 4],  # Monday to Friday
        "timezone": "America/New_York",
    },
    "deployment_tools": {
        "blocked_during": ["change-freeze"],  # Checked against a feature flag
    },
}
```

## Pattern 6: Output Filtering

Permissions are not just about what the AI can access. They are also about what the AI can return.

**The risk:** The AI has read access to a database that contains both public and confidential fields. The AI reads the full record and includes confidential fields in its response to a user who should not see them.

**Implementation:**

```python
OUTPUT_FILTERS = {
    "ai-assistant-readonly": {
        "strip_fields": ["ssn", "salary", "internal_notes", "security_clearance"],
        "redact_patterns": [r"\b\d{3}-\d{2}-\d{4}\b"],  # SSN pattern
        "max_records_per_response": 10,
    }
}
```

Apply output filters at the MCP server level, not at the AI prompt level. Prompt-level instructions are not reliable access controls.

## Pattern 7: Cascading Permissions

When your MCP server calls another service that also has its own permission model, the permissions must cascade correctly.

**Example:** AI > MCP Server > Internal API > Database

The MCP server authenticates the AI. The internal API authenticates the MCP server. The database authenticates the internal API.

At each hop, the effective permissions should be the intersection (most restrictive) of all layers, not any single layer.

**Anti-pattern:** The MCP server uses a service account with broad access to the internal API, bypassing the user-level permissions. This means the AI effectively has more access than the human user.

**Fix:** Pass the user context (or token) through every hop. Each layer evaluates permissions against the original user's access level, not the service account's.

## Quick Reference

| Pattern | Protects Against | Complexity |
|---------|-----------------|------------|
| Least Privilege | Over-exposure of tools | Low |
| Role-Based | Wrong user accessing wrong tools | Low |
| Resource ACLs | Cross-department data leakage | Medium |
| Operation Segregation | Write-path prompt injection | Medium |
| Temporal Scoping | Off-hours misuse | Medium |
| Output Filtering | Sensitive data in responses | Medium |
| Cascading Permissions | Privilege escalation across hops | High |

Start with Least Privilege and Role-Based. Add the others as your deployment matures and your security team requires them.
