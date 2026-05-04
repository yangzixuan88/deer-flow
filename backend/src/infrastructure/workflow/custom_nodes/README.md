# n8n Custom Nodes - Hot-Mounting Repository

This directory is mapped into the `n8n` container as `/home/node/.n8n/custom`. 
All nodes placed here will be automatically loaded by the n8n execution engine upon restart.

## 📦 Directory Structure

- `package.json`: Definies the custom node package.
- `dist/`: Compiled node files (for production-grade nodes).
- `index.js`: Entry point for the custom extensions.

## 🛠️ Automated Skill Packing (F8.2)

The `Skill-Packing System` automatically populates this folder with new custom nodes derived from successful Agent-driven workflows. 
To reload nodes, the `AAL` will trigger a graceful container restart (unless internal dynamic loading is enabled via n8n's internal workflow system).
