# OpenClaw 2.0 Omni-Empowerment MCP Server

This server exposes the "Nine-Dimensional Assets" accumulated in your project as standard **Model Context Protocol (MCP)** tools. This allows other AI agents (like Claude Desktop or Cursor) to directly retrieve optimized prompts, skills, and domain knowledge from your local repository.

## 🛠️ Configuration

To use this server in **Claude Desktop** or **Cursor**, add the following entry to your `mcpServers` configuration:

```json
{
  "mcpServers": {
    "openclaw": {
      "command": "python",
      "args": ["E:/OpenClaw-Base/openclaw超级工程项目/src/infrastructure/server/mcp_server.py"]
    }
  }
}
```

## 🧰 Available Tools

1. **`list_available_assets`**:
   - Lists all gold-level assets (Quality > 0.7) in the current environment.
   - Optional parameter: `asset_type` (e.g., `DomainKnowledge`, `Skill`).

2. **`get_optimized_prompt`**:
   - Retrieves the full content of an asset by name or partial name match.
   - Parameter: `asset_name`.

## 📂 Folder Structure

The server automatically resolves file content based on the `Asset_Manifest.sqlite` index and the following subdirectories:
- `assets/domain_knowledge/`
- `assets/cold_skills/`
- `assets/trace_logs/`
- `assets/warm_memories/`
