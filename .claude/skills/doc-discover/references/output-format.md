# 输出格式

本文档定义 doc-discover 执行完成后生成的健康监测报告格式。报告直接打印到终端，同时将新发现的任务写入 `$PROJECT_ROOT/_meta/task-queue.yaml`（读写协议见 `$PROJECT_ROOT/_meta/task-schema.md`，写入后须重新生成 `task-queue.md`），并追加记录到 `$PROJECT_ROOT/_meta/research-log.md`。

## 健康监测报告模板

```markdown
# 文档健康监测报告 — {日期}

## 健康度概览

| 维度 | 状态 | 发现数 |
|------|------|--------|
| 模块覆盖 | {OK/WARN} | {N} 个新模块 |
| 源码漂移 | {OK/WARN} | {N} 篇文档漂移 HIGH |
| 类型平衡 | {OK/WARN} | {N} 个象限不足 |
| 横切主题 | {OK/INFO} | {N} 个候选主题 |
| 深度匹配 | {OK/WARN} | {N} 篇深度不足 |
| 角色覆盖 | {OK/WARN} | {N} 个场景未覆盖 |
| 验证债务 | {OK/INFO} | {N} 个待验证点 |

## 新增任务

| ID | 优先级 | 类型 | 目标文件 | 来源模式 | 说明 |
|----|--------|------|---------|---------|------|
| ... | ... | ... | ... | drift/balance/themes/depth | ... |

## 建议

{按优先级排序的下一步行动建议}
```

## 字段说明

**状态列**取值：
- `OK`：该维度无异常发现
- `WARN`：发现需要关注的问题
- `INFO`：有信息性发现，但不一定需要立即行动

**来源模式列**标注任务由哪个检测模式产出，便于溯源：
- `modules` / `drift` / `balance` / `themes` / `depth` / `personas` / `verify`（基础模式 1-7）
- `journeys` / `failures` / `coupling` / `temporal` / `decisions` / `tribal`（深层模式 8-13）

**新增任务**中的 ID 应与写入 `$PROJECT_ROOT/_meta/task-queue.yaml` 的任务 ID 一致。
