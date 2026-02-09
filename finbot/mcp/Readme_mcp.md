# MCP Design Overview

## Objective

The goal of this MCP design is to **control how agents access tools**, without changing how agents think or behave.

This design ensures that:

- Agents focus only on **reasoning and decision-making**
- Tool access is **explicitly declared and enforced by the framework**
- MCP servers remain **simple executors**
- All activity is **observable for security review**

In short, **MCP is introduced to separate agent logic from tool execution**, while keeping the existing **multi-agent CTF flow intact**.

---

## Core Architecture Principles

### 1. Framework-Controlled Access

Agents **never call MCP servers directly**.  
All tool calls must go through the **framework-controlled interface**.

This ensures:
- Centralized policy enforcement
- Consistent auditing and telemetry
- No direct coupling between agents and tools

---

### 2. Agent-Scoped Tool Visibility

Each agent **explicitly declares** which MCP servers it is allowed to use.

- Agents can only see tools within their declared scope
- Tools outside this scope are completely invisible to the agent
- Unauthorized tool calls are blocked at the framework level

---

### 3. Passive MCP Servers

MCP servers are **pure execution layers**.

They:
- Expose tools
- Execute incoming requests

They do **not**:
- Know which agent is calling them
- Understand permissions or policy
- Make authorization decisions

---

### 4. Separation of Concerns

The system strictly separates responsibilities:

- **Agent logic** → reasoning and decision-making
- **Tool execution** → handled by MCP servers
- **Application startup & wiring** → handled by the framework

This keeps each layer simple, testable, and replaceable.

---

### 5. Minimal Enforcement Model

All access control is enforced at the **MCP Client / Host interface**.

- No policy logic exists inside agent code
- No enforcement logic exists inside MCP servers
- This minimizes complexity and reduces attack surface

---

### 6. Mandatory Observability

Every tool interaction is captured through **telemetry**:

- Tool access attempts
- Successful executions
- Failures and denials

Observability is:
- Always enabled
- Non-intrusive
- Does not affect execution flow

This enables auditing, debugging, and security reviews without changing agent behavior.

```text

UI / API / Cloud Function
            |
            v
     MCP Orchestrator
            |
            v
+-------------------------------+
|       MCP Framework           |
|                               |
|  - MCPRegistry                |
|  - AgentToolRegistrationResolver
|  - MCPHost                     |
|  - Telemetry                   |
+---------------+---------------+
                |
                | MCP protocol
                v
+-------------------+   +-------------------+
| Payments MCP      |   | Drive MCP         |
| Server            |   | Server            |
+-------------------+   +-------------------+

                |
                v
+-----------------------------------+
|           Agents                  |
|                                   |
| ReconAgent → OffensiveAgent →     |
| AuditorAgent                      |
+-----------------------------------+
```

## Component Responsibilities

| Component | Responsibility |
|---------|----------------|
| **Agent** | Reasoning, decision-making, and declaring tool-call intent |
| **AgentToolRegistrationResolver** | Dependency discovery and agent-scoped tool wiring |
| **MCPHost** | Central authority for routing requests and enforcing access |
| **MCPClient** | Scoped execution interface injected into agents |
| **MCPRegistry** | Source of truth for MCP server discovery and lookup |
| **Telemetry** | Passive observability layer capturing all activity |
| **MCP Orchestrator** | Coordinates lifecycle from startup to teardown |


---

## Execution Lifecycle

This section describes how MCP execution proceeds from initialization to completion.

### 1. Registration

MCP servers are registered with the **MCPRegistry**.

- The registry stores **connection objects only**
- It contains **no policy or authorization logic**

---

### 2. Declaration

Agents declare the MCP servers they require using `required_mcp_servers`.

- This declaration is **explicit**
- The configuration is **static and deterministic**
- No dynamic discovery is allowed at runtime

---

### 3. Resolution

The **AgentToolRegistrationResolver** performs the following steps:

- Reads agent declarations
- Validates them against the MCPRegistry
- Creates a **scoped MCPClient** per agent
- Injects the MCPClient into the agent
- Registers the agent–client binding with the **MCPHost**

This step establishes **hard security boundaries** between agents and tools.

---

### 4. Execution

During execution:

- Agents invoke tools via the **MCPClient**
- The MCPClient enforces **server scope**
- The MCPHost validates agent registration and routes calls
- Telemetry records **tool attempts and results**
- MCP servers execute tools and return responses

Agents never:

- Discover MCP servers
- Access global tool sets
- Bypass framework enforcement

---

### 5. Teardown

At completion, the **MCP Orchestrator**:

- Finalizes execution
- Collects telemetry
- Emits `ctf_report.json`


## Folder Structure

```text
finbot/
├── main.py                      # Application entrypoint (unchanged)
│
├── mcp_runtime/
│   └── orchestrator.py          # MCP execution controller
│
├── mcp/
│   ├── host.py                  # Enforcement & routing
│   ├── resolver.py              # Dependency wiring
│   ├── client.py                # Scoped MCP execution
│   ├── registry.py              # MCP server registry
│   ├── telemetry.py             # Observability
│   └── Readme_mcp.md            # This RFC
│
├── agents_mcp/
│   ├── base_mcp_agent.py
│   ├── recon_agent.py
│   ├── offensive_agent.py
│   └── auditor_agent.py
│
├── mock_mcp_servers/
│   ├── payments_mcp/
│   └── drive_mcp/

```
