# 02｜接入顺序

## Phase A｜落盘与装载
1. 放置 `config/`、`prompts/`、`examples/`
2. 实现 YAML loader
3. 实现 Prompt loader
4. 实现 runtime state initializer

## Phase B｜最小运行
1. 实现 prompt assembly
2. 实现固定轮序调用
3. 实现 structured output parser
4. 实现 dossier writer

## Phase C｜执行闭环
1. evidence pods
2. execution lease
3. validation dispatch
4. reopen loop

## Phase D｜展示与学习
1. Feishu rendering
2. nightly learning handoff

## 关键原则
- 先旁路接入
- 先最小闭环
- 先写 dossier
- 最后接外部展示和学习闭环
