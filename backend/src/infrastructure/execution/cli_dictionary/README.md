# CLI-Anything 开源指令映射词典 (Dictionary)

本项目遵从老板要求的 **【铁则 4：GitHub 优先】**，优先集成 GitHub 上最顶尖的开源项目 `HKUDS/CLI-Anything` (29.3k stars)，通过其成熟的 **Harness** (软件马甲) 体系，将 Windows 常用软件映射为 AI 智能体可直接调用的 CLI 指令，极大地减少了对 DOM 树或视觉识别 (Visual-only) 的依赖。

## 📖 核心词典映射 (Core Mapping Dictionary)

| 软件名称 | CLI 接入点 (Entry Point) | 核心功能映射 (Key Mappings) |
| :--- | :--- | :--- |
| **Microsoft Office (via LibreOffice)** | `cli-anything-libreoffice` | 创建/编辑文档, PDF/XLSX/DOCX 格式转换, 文本/表格提取 |
| **WeChat (via nanobot)** | `nanobot wechat` | 消息收发, 媒体文件处理, 统一登录 CLI |
| **GIMP** | `cli-anything-gimp` | 图像滤镜应用, 图层管理, 批量处理, 格式转换 |
| **Draw.io** | `cli-anything-drawio` | 流程图/拓扑图创建与导出, XML 图表处理 |
| **Zoom** | `cli-anything-zoom` | 会议日程安排, 用户权限管理, 自动化通信 |
| **OBS Studio** | `cli-anything-obs-studio` | 推流/录屏控制, 场景源动态切换 |
| **Zotero** | `cli-anything-zotero` | 文献引用管理, 数据库条目查询 |

## 🛠️ 部署说明 (Deployment)

1. **词典定义**：所有映射集均定义在 `mapping_dictionaries.json` 中。
2. **应用集成**：后续 AAL (Autonomous Agent Layer) 在执行任务时，会首选本词典中的 CLI 指令，而非尝试进行高成本的视觉识别。
3. **扩展性**：可通过 `pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=xxx/agent-harness` 动态添加新的软件马甲。

---
**Status**: [DONE] Phase 3 - Execution Foundation (Pre-set Mappings)
