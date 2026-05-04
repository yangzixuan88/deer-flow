# RTCM 接入配置汇总包 v1.1（审计修正版）

这是给 **VSCode + Claude Code** 接入使用的 RTCM 工程包审计修正版。  
这版已经做过一次针对：

- 结构一致性
- 内容一致性
- 样例完整性
- Claude Code 可施工性

的全方位检查与修正。

## 关键变化

相比上一版，本版修复了：

- 角色注册字段缺失
- agent registry 运行级字段不足
- issue debate protocol 细节缺失
- prompt loader 路径写死
- project dossier 样例缺文件
- runtime orchestrator 过于瘦身
- feishu rendering 过于瘦身

## 建议接入目录

推荐落到你的项目仓中：

```text
./rtcm/
```

如果你后续要和 DeerFlow 用户目录长期绑定，再映射到：

```text
~/.deerflow/roundtable/
```

## 包内内容

- `docs/`：说明、接入顺序、Claude Code 工作流、体检报告
- `config/`：完整版 YAML 配置
- `prompts/`：10 个角色 Prompt
- `examples/`：完整样例项目 dossier
- `validate_bundle.py`：工程包自检脚本

## 推荐流程

1. 让 Claude Code 先只读 `docs/` 和 `config/integration_manifest.yaml`
2. 让它输出实际接入点建议，不要立刻大改
3. 先做：
   - config loader
   - prompt loader
   - runtime state initializer
   - dossier writer
   - minimal orchestrator skeleton
4. 最后再接 Feishu 和夜间复盘
