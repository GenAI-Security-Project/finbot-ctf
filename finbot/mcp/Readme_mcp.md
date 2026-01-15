## Objective

1. step1: build couple of mock mcp servers  
2. step2 : build the connectivity engine/layer (mcp host should be part of finbot to run and connect to above)  
3. step 3: specialized agent to leverage mcp use cases  



This document outlines the architecture, implementation steps, and security considerations for the Model Context Protocol (MCP) integration within FinBot.



---

## 1. Core Architecture Principles
* **MCP Host as the Sole Bridge:** The MCP Host is the only bridge between FinBot and MCP.
* **Isolated Agents:** Agents never talk to MCP servers directly; they interact only with the Host layer.

---

##

## High-Level Architecture Flow

### Execution Entry Point

```text
Execution Entry Point
        |
        v
+----------------------+
|      MCP Host        |  ← Connectivity Engine inside FinBot
|   (Central Gateway)  |
+----------+-----------+
           |
           v
+----------------------+        +----------------------+
|  Mock Payments MCP   |        |   Mock Drive MCP     |
|   (Stripe-like)      |        |   (Storage-like)     |
+----------------------+        +----------------------+

           |
           v
+-----------------------------------------------+
|        Specialized Agents                     |
|        (Use MCP via the Host)                 |
|                                               |
|   Recon Agent → Offensive Agent → Auditor     |
+-----------------------------------------------+

           |
           v
+----------------------+
| Telemetry & Report   |
|   ctf_report.json    |
+----------------------+
```

## 2. Step-by-Step Implementation

### Step 1: Build Mock MCP Servers
Build a small number of mock MCP servers, intentionally limited to simulate real-world service behavior and vulnerabilities.

| Server | What it simulates | Purpose |
| :--- | :--- | :--- |
| **Payments MCP** | Stripe-like payment workflows | Test idempotency and financial logic |
| **Drive MCP** | File storage with access control | Test authorization and data leakage |

**Server Requirements:**
* Implement real MCP tools.
* Behave like real production services.
* Contain intentional vulnerabilities (Exploitable by design).

### Step 2: Build the Connectivity Engine (MCP Host)
The MCP Host is the connectivity and control layer inside FinBot. It acts as the runtime environment for all MCP interactions.

**The Host Functions:**
* **Registration:** Registers MCP servers (mock today, real tomorrow).
* **Session Management:** Manages active MCP sessions and connections.
* **API Exposure:** Provides a simplified API to agents:
    * `list_tools(server)`
    * `call_tool(server, tool, args)`

**Abstraction:**
Agents remain unaware of how MCP works internally, how servers are started, or whether the servers are mock or production-grade.

### Step 3: Specialized Security Agents
These agents consume MCP tools to simulate usage and stress-test the ecosystem.

#### A. Recon Agent — “What is exposed?”
* **Purpose:** Discover the MCP attack surface.
* **Actions:** Enumerates tools, extracts parameters, and flags high-risk tools (refund, read, delete).
* **Key Question:** “What can an attacker learn just by connecting?”

#### B. Offensive Agent — “What can be abused?”
* **Purpose:** Exploit business logic flaws, not software bugs.
* **Actions:** Chains legitimate tools and exploits missing controls (e.g., Double Refund via missing idempotency or File Read via BOLA).
* **Key Question:** “What damage is possible using only allowed tools?”

#### C. Auditor Agent — “Is this safe to trust?”
* **Purpose:** Convert exploits into security decisions.
* **Actions:** Aggregates results and assigns a final verdict: **SECURE** or **COMPROMISED**.
* **Key Question:** “Can FinBot safely integrate this MCP ecosystem?”

---

## 3. Vulnerabilities & Logic Flaws

### Missing Idempotency (Double Refund)
* **Definition:** Operations that should run once can be triggered multiple times.
* **MCP Risk:** AI agents often retry on partial failures or repeat similar calls. Without idempotency, a retry becomes a duplicate financial transaction.

### BOLA (Broken Object Level Authorization)
* **Definition:** The system fails to check if the user has permission for a specific object/ID.
* **MCP Risk:** If an agent can guess a filename or ID, it can access data it shouldn't, leading to leaks.

---

## 4. Telemetry & Reporting
The system generates a `ctf_report.json` to record:
* **Recon findings:** Tools discovered and risks flagged.
* **Exploit attempts:** Success/failure of chained tool attacks.
* **Audit decisions:** Final security scoring.

---

## 5. Project Folder Structure

```text
finbot/
├── agents_mcp/
│   ├── base_mcp_agent.py     # Shared agent utilities
│   ├── recon_agent.py        # Tool discovery & risk flagging
│   ├── offensive_agent.py    # Exploit logic
│   ├── auditor_agent.py      # Blue-team analysis
│   └── __init__.py
│
├── mcp/
│   ├── host.py               # MCP runtime & server orchestration
│   ├── registry.py           # MCP server registry (source of truth)
│   ├── telemetry.py          # Central event logging
│   ├── Readme_mcp.md         # MCP-specific notes
│   └── __init__.py
│
├── mock_mcp_servers/
│   ├── payments_mcp/
│   │   ├── server.py         # Vulnerable payments service
│   │   └── vulnerabilities.yaml
│   │
│   ├── drive_mcp/
│   │   ├── server.py         # Vulnerable file service
│   │   ├── mock_data/
│   │   │   └── secret.txt
│   │   └── vulnerabilities.yaml