# 03｜VSCode + Claude Code 工作流

## 推荐分支
```bash
git checkout -b feature/rtcm-integration-v1
```

## Claude Code 推荐节奏

### 第 1 轮：只读理解
读：
- docs/*
- config/integration_manifest.yaml

输出：
- 接入点建议
- 新增文件清单
- 风险点

### 第 2 轮：骨架施工
只做：
- config loader
- prompt loader
- runtime state initializer
- dossier writer

### 第 3 轮：讨论流
做：
- prompt assembly
- fixed speaking order
- parser
- issue state machine

### 第 4 轮：执行流
做：
- evidence pods
- execution lease
- validation
- reopen

### 第 5 轮：展示与学习
做：
- Feishu rendering
- nightly exports
