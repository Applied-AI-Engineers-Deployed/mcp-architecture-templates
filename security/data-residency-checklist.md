# Data Residency Checklist for Enterprise MCP Deployments

Run through this checklist before deploying any MCP server that touches production data. Skipping this will not save you time. It will cost you a security review rejection and a 2-week delay.

## 1. Data Classification

- [ ] Identify every data type the MCP server will access (PII, financial, health, internal docs, etc.)
- [ ] Map each data type to your org's sensitivity classification (public, internal, confidential, restricted)
- [ ] Document which data types will pass through the MCP server vs. which will be referenced by ID only
- [ ] Confirm whether any data types are subject to specific regulations (GDPR, HIPAA, SOX, CCPA)

## 2. Data Flow Mapping

- [ ] Diagram the complete data flow: source system > MCP server > AI interface > response path
- [ ] Identify every network hop where data is in transit
- [ ] Identify every location where data is at rest (even temporarily, like logs or caches)
- [ ] Confirm that no data is being cached or stored in unexpected locations (container volumes, temp files, log aggregators)

## 3. Geographic Constraints

- [ ] Identify which geographic regions your data is allowed to reside in
- [ ] Confirm that the MCP server and all downstream services run in compliant regions
- [ ] Verify that the AI interface (Claude, OpenAI, internal model) processes data in compliant regions
- [ ] Check whether any third-party services in the pipeline route data through non-compliant regions
- [ ] If using cloud providers, confirm region lock is configured (not just default region selection)

## 4. AI-Specific Data Residency Concerns

- [ ] Confirm whether the AI provider retains prompts or completions (and if so, where)
- [ ] Verify that tool call payloads (the data sent via MCP) are not retained by the AI provider for training
- [ ] Check whether the AI provider's data processing agreement (DPA) covers your data classification level
- [ ] If using a self-hosted model, confirm the model inference infrastructure is in a compliant region

## 5. Logging and Audit Trail

- [ ] Audit logs include enough context to reconstruct what data was accessed, by whom, and when
- [ ] Audit logs themselves are stored in compliant regions
- [ ] Logs do not contain raw sensitive data (log the operation and record ID, not the record content)
- [ ] Log retention policies comply with regulatory requirements
- [ ] Logs are immutable or append-only to prevent tampering

## 6. Encryption

- [ ] Data is encrypted in transit between every service in the pipeline (TLS 1.2+)
- [ ] Data is encrypted at rest at every storage location
- [ ] Encryption keys are managed through your org's key management system (not hardcoded)
- [ ] Key rotation is configured and tested

## 7. Incident Response

- [ ] You have a documented process for what happens if data is accessed from a non-compliant region
- [ ] The security team knows the MCP deployment exists and how to shut it down if needed
- [ ] There is a kill switch to disable the MCP server without taking down dependent systems
- [ ] Contact information for the data protection officer (or equivalent) is documented

## 8. Ongoing Compliance

- [ ] Data residency is re-validated when infrastructure changes (new regions, new providers, new services)
- [ ] Changes to the AI provider's data handling policies are monitored
- [ ] Periodic audits are scheduled (quarterly at minimum)
- [ ] The MCP server's data flow documentation stays current as the architecture evolves
