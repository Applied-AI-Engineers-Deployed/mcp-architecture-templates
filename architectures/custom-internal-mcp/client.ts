/**
 * Custom MCP Client
 *
 * TypeScript client for connecting to the custom internal MCP server
 * with proper authentication handling.
 *
 * Adapt the auth provider to your identity system (Okta, Azure AD, Auth0, etc.)
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

interface MCPClientConfig {
  serverCommand: string;
  serverArgs: string[];
  authToken?: string;
  maxRetries: number;
  retryDelayMs: number;
  requestTimeoutMs: number;
}

const DEFAULT_CONFIG: MCPClientConfig = {
  serverCommand: "python",
  serverArgs: ["server.py"],
  maxRetries: 3,
  retryDelayMs: 1000,
  requestTimeoutMs: 30000,
};

// ---------------------------------------------------------------------------
// Auth Provider (adapt to your identity provider)
// ---------------------------------------------------------------------------

interface AuthProvider {
  getToken(): Promise<string>;
  refreshToken(): Promise<string>;
}

/**
 * REPLACE THIS with your actual auth provider.
 *
 * Examples:
 * - OktaAuthProvider that exchanges client credentials for a JWT
 * - AzureADAuthProvider that uses managed identity
 * - Auth0AuthProvider that uses machine-to-machine tokens
 */
class StaticTokenAuthProvider implements AuthProvider {
  constructor(private token: string) {}

  async getToken(): Promise<string> {
    return this.token;
  }

  async refreshToken(): Promise<string> {
    // In production, this would request a fresh token from your IdP
    return this.token;
  }
}

// ---------------------------------------------------------------------------
// MCP Client Wrapper
// ---------------------------------------------------------------------------

class EnterpriseClient {
  private client: Client;
  private transport: StdioClientTransport | null = null;
  private config: MCPClientConfig;
  private authProvider: AuthProvider;
  private connected = false;

  constructor(config: Partial<MCPClientConfig> = {}, authProvider: AuthProvider) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.authProvider = authProvider;
    this.client = new Client(
      { name: "enterprise-mcp-client", version: "1.0.0" },
      { capabilities: {} }
    );
  }

  /**
   * Connect to the MCP server.
   */
  async connect(): Promise<void> {
    if (this.connected) {
      console.log("[MCP Client] Already connected");
      return;
    }

    console.log("[MCP Client] Connecting to MCP server...");

    const token = await this.authProvider.getToken();

    this.transport = new StdioClientTransport({
      command: this.config.serverCommand,
      args: this.config.serverArgs,
      env: {
        ...process.env,
        AUTH_TOKEN: token,
      },
    });

    await this.client.connect(this.transport);
    this.connected = true;
    console.log("[MCP Client] Connected successfully");
  }

  /**
   * Disconnect from the MCP server.
   */
  async disconnect(): Promise<void> {
    if (!this.connected) return;
    await this.client.close();
    this.connected = false;
    console.log("[MCP Client] Disconnected");
  }

  /**
   * List all available tools from the server.
   */
  async listTools(): Promise<any[]> {
    this.ensureConnected();
    const result = await this.client.listTools();
    return result.tools;
  }

  /**
   * Call a tool with retry logic.
   *
   * Retries on transient failures (network issues, rate limits).
   * Does NOT retry on permission denied or validation errors.
   */
  async callTool(toolName: string, args: Record<string, any>): Promise<any> {
    this.ensureConnected();

    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.config.maxRetries; attempt++) {
      try {
        console.log(
          `[MCP Client] Calling '${toolName}' (attempt ${attempt}/${this.config.maxRetries})`
        );

        const result = await this.withTimeout(
          this.client.callTool({ name: toolName, arguments: args }),
          this.config.requestTimeoutMs
        );

        // Parse the response
        const content = result.content as any[];
        if (!content || content.length === 0) {
          throw new Error("Empty response from server");
        }

        const textContent = content.find((c: any) => c.type === "text");
        if (!textContent) {
          throw new Error("No text content in response");
        }

        const parsed = JSON.parse(textContent.text);

        // Check for permission or validation errors (do not retry these)
        if (parsed.error) {
          const errorMsg = parsed.error as string;
          if (
            errorMsg.includes("Permission denied") ||
            errorMsg.includes("Access denied")
          ) {
            throw new PermissionError(errorMsg);
          }
          if (errorMsg.includes("Rate limit")) {
            console.log(`[MCP Client] Rate limited, waiting before retry...`);
            await this.delay(this.config.retryDelayMs * attempt);
            lastError = new Error(errorMsg);
            continue;
          }
          throw new Error(errorMsg);
        }

        return parsed;
      } catch (error) {
        if (error instanceof PermissionError) {
          throw error; // Do not retry permission errors
        }
        lastError = error as Error;
        if (attempt < this.config.maxRetries) {
          const delay = this.config.retryDelayMs * attempt;
          console.log(
            `[MCP Client] Attempt ${attempt} failed: ${lastError.message}. Retrying in ${delay}ms...`
          );
          await this.delay(delay);
        }
      }
    }

    throw new Error(
      `Failed after ${this.config.maxRetries} attempts. Last error: ${lastError?.message}`
    );
  }

  // -------------------------------------------------------------------------
  // Convenience Methods
  // -------------------------------------------------------------------------

  async getRecord(recordId: string): Promise<any> {
    return this.callTool("get_record", { record_id: recordId });
  }

  async searchRecords(query: string, maxResults?: number): Promise<any> {
    const args: Record<string, any> = { query };
    if (maxResults !== undefined) args.max_results = maxResults;
    return this.callTool("search_records", args);
  }

  async getSchema(): Promise<any> {
    return this.callTool("get_schema", {});
  }

  async createRecord(data: Record<string, any>): Promise<any> {
    return this.callTool("create_record", { data });
  }

  async updateRecord(
    recordId: string,
    data: Record<string, any>
  ): Promise<any> {
    return this.callTool("update_record", { record_id: recordId, data });
  }

  async deleteRecord(recordId: string): Promise<any> {
    return this.callTool("delete_record", { record_id: recordId });
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  private ensureConnected(): void {
    if (!this.connected) {
      throw new Error("Client not connected. Call connect() first.");
    }
  }

  private async withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error(`Request timed out after ${ms}ms`)), ms)
      ),
    ]);
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

class PermissionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PermissionError";
  }
}

// ---------------------------------------------------------------------------
// Usage Example
// ---------------------------------------------------------------------------

async function main() {
  // REPLACE: Use your real auth provider
  const auth = new StaticTokenAuthProvider("readonly-token");

  const client = new EnterpriseClient(
    {
      serverCommand: "python",
      serverArgs: ["server.py"],
      maxRetries: 3,
      retryDelayMs: 1000,
      requestTimeoutMs: 30000,
    },
    auth
  );

  try {
    await client.connect();

    // List available tools
    const tools = await client.listTools();
    console.log("Available tools:", tools.map((t: any) => t.name));

    // Get schema
    const schema = await client.getSchema();
    console.log("Schema:", schema);

    // Search records
    const results = await client.searchRecords("quarterly report", 10);
    console.log("Search results:", results);

    // Get a specific record
    const record = await client.getRecord("record-123");
    console.log("Record:", record);
  } catch (error) {
    if (error instanceof PermissionError) {
      console.error("Permission denied:", error.message);
    } else {
      console.error("Error:", error);
    }
  } finally {
    await client.disconnect();
  }
}

main();
