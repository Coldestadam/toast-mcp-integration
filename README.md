# Toast MCP Integration

## 1. Overview
This project provides a **Model Context Protocol (MCP) server** that integrates with the **Toast API**. It enables Claude Desktop to interact with Toast data (such as products and sales) through MCP tools. The server is implemented in Python and uses [`uv`](https://github.com/astral-sh/uv) for environment and dependency management.

---

## 2. Setup and Run

### 2a. Installation of `uv` and Running the Project
1. Install [uv](https://github.com/astral-sh/uv) if not already installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Clone this repository:
   ```bash
   git clone https://github.com/your-username/toast-mcp-integration.git
   cd toast-mcp-integration
   ```
3. Run the MCP server:
   ```bash
   uv run toast_mcp_server.py
   ```

**Note on Dependencies:**  
You do not need a `requirements.txt` file when using `uv`. Dependencies are managed through `pyproject.toml` and locked in `uv.lock`. This ensures reproducible environments.  
If contributors prefer `pip`, they can generate a `requirements.txt` with:  
```bash
uv export > requirements.txt
```

---

### 2b. Environmental Variables
The project requires environment variables for Toast API authentication.

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```
2. Fill in the required values in `.env`:
   - `TOAST_API_KEY` (or other credentials depending on your setup)
   - Any additional variables required by `toast_api_client.py`

---

### 2c. MCP Config Editing and Integration
To integrate with **Claude Desktop**, you need to edit its configuration file.

1. Locate Claude Desktop’s config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `C:\Users\<YourUsername>\AppData\Roaming\Claude\claude_desktop_config.json`

2. Add the following snippet to the `"mcpServers"` section (replace placeholders with your actual paths):
   ```json
   {
     "mcpServers": {
       "toast-mcp": {
         "command": "/absolute/path/to/uv",   // Use `which uv` (macOS/Linux) or `where uv` (Windows)
         "args": [
           "--directory",
           "/absolute/path/to/toast-mcp-integration",  // Replace with your cloned repo path
           "run",
           "toast_mcp_server.py"
         ]
       }
     }
   }
   ```

   - **`command`**: Path to the `uv` executable.  
     - On macOS/Linux, run `which uv` to find it.  
     - On Windows, run `where uv` to find it.  
   - **`--directory`**: Path to your cloned repo directory. Replace the placeholder with your actual path.

3. Restart Claude Desktop. The Toast MCP server should now be available.

---

## 3. Open Questions (Personal Reflections)

### 3a. Architecture Decisions
*Placeholder: Describe why you chose the MCP server structure, how you organized tools (`tools/products.py`, `tools/sales.py`), and why you used `uv`.*

### 3b. Toast Authentication
*Placeholder: Explain how you handled Toast authentication (API keys, OAuth, etc.) and any security considerations.*

### 3c. Challenges and Solutions
*Placeholder: Document challenges you faced (e.g., rate limits, schema mismatches, debugging MCP integration) and how you solved them.*

### 3d. Performance Considerations
*Placeholder: Describe how you optimized API calls, caching, batching, or other performance strategies.*

### 3e. What You’d Add With More Time
*Placeholder: List future improvements (e.g., more endpoints, analytics, error handling, monitoring).*
