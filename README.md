# Toast MCP Integration

## 1. Overview
This project provides a **Model Context Protocol (MCP) server** that integrates with the **Toast API**. It enables Claude Desktop to interact with Toast data (such as products and sales) through MCP tools. The server is implemented in Python and uses [`uv`](https://github.com/astral-sh/uv) for environment and dependency management.

### Available Tools
- **`get_sales_summary`** – Summarizes sales within a timeframe, including total revenue, total items sold, and item-level breakdowns.  
- **`get_top_items`** – Returns the top-selling items over the past `n` days, ranked by quantity sold and revenue.  
- **`get_product_mix`** – Groups sales by product category to show the mix of items sold and their revenue contribution.  

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
I placed my keys in an `.env` file that is forbidden to be pushed to github using `.gitignore`. I did provide a `.env.example` file of the environmental variables that will work with my code, its the responsibility of the developer to place the secrets they recieved into the file.

### 3c. Challenges and Solutions
There were many challenges to this project, below is a list!
1. Token Expiry
   * Problem: The Oauth2 token that Toast API services provides expires in 24 hours, not the original 5 hours as stated in the project pdf
   * Solution: When building API Client, authorizing the client everytime gave a token and an expire time given by the API service itself. I made sure in the case the server was running while it is about to expire, Toast API services allow us to generate a new token a miniute before expiring.
2. Bug Encountered in the [`/orders/v2/ordersBulk`](https://doc.toasttab.com/openapi/orders/operation/ordersBulkGet/) API endpoint in being able to get all ordered items
   * Problem: There are nested fields where we extract items from orders, but for some reason the output json schema allows nested items within items. Therefore some items were excluded from my code to exract it in function `get_orders_df()` in `utils/client_utils.py`.
   * Solution: After seeing that bug, I made sure to extract those nested items as well.
3. When trying the `get_sales_summary()` tool in MCP Inspector, I get this error: `MCP error -32001: Request timed out`
   * Problem: There was a Request Timeout for when I was trying tool `get_sales_summary()` to extract sales data that was for a timeframe of a month.
   * Solution: The MCP Client configuration of the MCP Instructor is changeable, the RequestTimeout was set to 60,000ms (60 sec) instead of (30 sec)
4. Configuring Tools to filter by restaurant felt useless since there is only two active buisnesses
   * Problem: I created my tools and overall Data Structure to be able to fiter by restaurant, since there were a total of 8-9 menus given by the [`/menus/v2/menus`](https://doc.toasttab.com/openapi/menus/operation/menusGet/) endpoint.
   * Solution: No solution, just something I encountered.
5. The Menu Resource is not being reached within Claude Desktop with Human Messages
   **Something to work on**
6. Overall Data Structure
   * Problem: Took a lot of time to figure out what was the best way to extract information from Toast API services! The JSON Schemas of both the `/menus/v2/menus` and `/orders/v2/ordersBulk` were not documented well and super huge to have to sift through by hand. It was hard then to organize myself, with all information to see how to construct organized Data Table Schemas (Or in my case Pandas Dataframes).
   * Solution: Wednesday night, I took out my notebook and by hand wrote all the requirements of the tools and figured out when data it needs to be answered, which a lot of the tools had overlapping requirements. Then I wrote all things I can extract from the endpoints, and wrote down how to access the datafields in the JSON Reponses of both endpoints. The ending solution was to have two tables, one for menus and for orders, where menus was not dependent on the tools but orders was extracted everytime by a tool call. The menu table was used to pair all ordered items to the name of the restaurant and the item group (category) of each item in orders.
   
### 3d. Performance Considerations
I did not have time to make this more efficient, but here are things I would try:
1. Use Relational SQL Databases for faster filtering and querying that is not dependent on Toast API
2. Use cache system to save requested ordered items (ex. For a time frame of 30 days) to be able to get data quick to answer sales questions that are more recent in time.
3. Use only SQL for Data Aggregation rather than Pandas

### 3e. What You’d Add With More Time
1. Implement the other tools
2. Give String Datatypes of the inputs and output schemas to the tools, and perhaps shorten the docstrings to make it easier for the model to know what tools to use.
2. Find other data analytical features that be extracted that can be useful, especially around customers
3. MAKE DATA PLOTS TO SHARE VISUALIZATIONS IN CLAUDE DESKTOP
4. Create a more efficient way to test this Server and interaction with Claude Desktop
5. Create a Visualization of Data Architecture
6. Improve this README
