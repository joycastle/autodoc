# Task Queue Schema 与读写协议

本文件定义 `task-queue.yaml` 的数据格式和所有 skill 的读写规则。任何修改任务队列的 skill 必须遵守本协议。

## 文件结构

```
_meta/
  task-queue.yaml      # 规范数据源（活跃任务）
  task-archive.yaml    # 已完成任务归档
  task-queue.md        # 自动生成的可读视图（禁止手动编辑）
  task-schema.md       # 本文件
  claims/              # 锁文件（分布式认领）
  contracts/           # Sprint Contract 文件
```

## YAML Schema

### task-queue.yaml

```yaml
meta:
  next_id: 79                          # 下一个可用 ID 数字
  updated_at: "2026-03-27T12:00:00+08:00"  # 最后修改时间

tasks:
  - id: "T-071"                        # 必填，格式 T-{NNN}
    priority: P1                       # 必填，P0 | P1 | P2
    type: improve                      # 必填，create | improve | verify
    target: sys-06-server-promo        # 必填，目标文件名（不含 .md）
    status: pending                    # 必填，见「状态流转」
    score: 23                          # 必填，预计算优先级分数
    roles:                             # 必填，受益角色列表
      - server-dev
    depends_on: []                     # 可选，依赖的任务 ID 列表
    batch: "git-arch"                  # 必填，来源批次标签
    description: "简要说明"             # 必填，任务描述
    claimed_at: null                   # 可选，in_progress 时设置，ISO 8601
    final_score: null                  # 可选，评估完成时设置，如 "11/12 (4/4)"
```

### task-archive.yaml

```yaml
tasks:
  - id: "T-001"
    target: sys-01-client-networking
    completed_at: "2026-03-25"         # 完成日期
    final_score: "12/12"               # 最终评分
    eval_method: "自评（旧流程）"       # 评估方式
```

## 状态流转

```
pending --> in_progress --> review_pending --> completed (归档)
    ^                            |
    +-------- improve <----------+
```

| 状态 | 含义 | 谁设置 |
|------|------|--------|
| pending | 等待认领 | doc-discover / doc-expert 创建时 |
| in_progress | 已被认领 | doc-research STEP 1 |
| review_pending | 撰写完成，等待评估 | doc-research STEP 5 |
| improve | 评估未通过，需改进 | doc-review（视同 pending，可被 doc-research 认领） |
| completed | 评估通过 | doc-review（从 queue 移除，写入 archive） |

## 优先级评分公式

```
score = 基础分 + 依赖分 + 角色分 + 类型分

基础分：P0=30, P1=20, P2=10
依赖分：被其他 pending 任务的 depends_on 引用 → +10
角色分：roles 数量 >=3 → +5，>=2 → +3
类型分：verify=+5, improve=+3, create=0

同分时：verify > improve > create，ID 数字小的优先
```

score 在任务创建时计算并写入，认领时 doc-research 可重新验证但通常直接使用。

## 读写协议

### 通用规则

1. **读取**：Read `_meta/task-queue.yaml`，解析 YAML
2. **写入**：修改内存中的数据 → Write 完整文件回 `task-queue.yaml` → 重新生成 `task-queue.md`
3. **归档**：completed 任务从 queue.yaml 移除 → 追加到 archive.yaml
4. **ID 分配**：读 `meta.next_id`，分配后递增写回
5. **时间戳**：统一使用 ISO 8601 带时区，如 `2026-03-27T12:00:00+08:00`
6. **tasks 列表排序**：按 score 降序排列（写入时排序）

### doc-research 协议

**认领（STEP 1）**：
1. 读取 `task-queue.yaml`
2. 过滤 `status: pending` 或 `status: improve` 的任务
3. 检查 `depends_on` 中所有 ID 是否已在 `task-archive.yaml` 中（即已完成）
4. 按 score 降序选择最高分任务
5. 更新该任务：`status: in_progress`，`claimed_at: {now}`
6. 写锁文件 `_meta/claims/T-{id}.lock`
7. 写回 YAML，生成 markdown

**交接（STEP 5）**：
1. 更新该任务：`status: review_pending`，清除 `claimed_at`
2. 如有衍生任务：追加到 `tasks` 列表，递增 `meta.next_id`
3. 删除锁文件
4. 写回 YAML，生成 markdown

### doc-review 协议

**评估通过**：
1. 从 `task-queue.yaml` 中移除该任务
2. 追加到 `task-archive.yaml`：`{id, target, completed_at, final_score, eval_method}`
3. 写回两个 YAML 文件，生成 markdown

**评估未通过**：
1. 更新该任务：`status: improve`，`final_score: "{score}"`
2. 写回 YAML，生成 markdown

### doc-discover / doc-expert 协议

**批量创建任务**：
1. 读取 `task-queue.yaml`
2. 从 `meta.next_id` 开始分配连续 ID
3. 追加新任务到 `tasks` 列表
4. 更新 `meta.next_id` 和 `meta.updated_at`
5. 按 score 降序重新排列 `tasks`
6. 写回 YAML，生成 markdown

## Markdown 生成模板

每次写入 `task-queue.yaml` 后，必须用以下模板重新生成 `task-queue.md`：

```markdown
<!-- AUTO-GENERATED from task-queue.yaml -- 禁止手动编辑 -->

# 文档任务队列

## 队列统计

| 指标 | 数值 |
|------|------|
| 活跃任务 | {count of tasks in queue} |
| 已归档 | {count of tasks in archive} |
| 最后更新 | {meta.updated_at 的日期部分} |

## 状态流转

pending -> in_progress -> review_pending -> completed（归档）
                                  ↓
                              improve（回到待认领）

## 活跃任务（按 score 降序）

| ID | P | 类型 | 目标文件 | score | 状态 | 受益角色 | 依赖 | 说明 |
|----|---|------|---------|-------|------|---------|------|------|
{for each task in tasks, sorted by score desc:}
| {id} | {priority} | {type} | {target} | {score} | {status} | {roles joined by ,} | {depends_on joined by , or -} | {description truncated to 60 chars} |

## 最近完成（最新 10 条）

| ID | 目标文件 | 完成时间 | 分数 | 评估方式 |
|----|---------|---------|------|---------|
{last 10 entries from task-archive.yaml, sorted by completed_at desc}

## ID 计数器

下一个 ID：T-{meta.next_id 的三位数格式}
```

description 在表格中截断到 60 字符以保持可读性；完整描述在 YAML 中保留。
