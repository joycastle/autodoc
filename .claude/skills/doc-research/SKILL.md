---
name: doc-research
description: "Autoresearch 文档研究循环。自主从任务队列中选取最高优先级任务，探索源码，撰写或改进文档。生成器角色，不自评。用 /doc-research 启动。"
---

# /doc-research — 文档生成器（Generator）

## 角色定位

本 skill 是 Generator-Evaluator 架构中的 **Generator**。职责是探索源码并撰写文档，但 **不评估自身产出质量**。评估由独立的 `/doc-review` 完成。分离生成与评估可避免同一 agent 自评的系统性偏差。

## 触发条件

用户输入 `/doc-research` 或要求「继续推进文档」「自动写文档」。

## 单次迭代流程

每次调用执行 **一个任务** 后结束（非无限循环）。状态通过文件交换，每次在干净上下文中启动。用户可用 `/loop 15m /doc-research` 实现连续自动推进。

```
STEP 1 — CLAIM

  **外部调度模式（推荐）**：当 prompt 中包含「已认领任务 T-XXX」时，
  说明任务已由外部调度器（autodoc.py）通过 claim-task.py 脚本原子认领，
  lock 文件已写入，YAML 已更新。此时跳过整个 STEP 1，直接从 STEP 2 开始。
  从 $PROJECT_ROOT/_meta/task-queue.yaml 读取 T-XXX 的详细信息（type, target, description 等）即可。

  **手动模式**（在交互式 Claude Code session 中手动执行 /doc-research 时）：
  用 Bash 执行认领脚本：
    `CLAIMED=$(python3 .claude/skills/doc-research/scripts/claim-task.py); echo "$CLAIMED"`
  IF CLAIMED 非空 → 认领成功，进入 STEP 2
  IF CLAIMED 为空 → 输出「无可认领任务」→ STOP
  IF 脚本失败 → 输出错误信息 → STOP（禁止手动认领替代）

STEP 2 — CONTRACT + EXPLORE（并行）

  根据任务类型选择探索策略，然后并行执行：

  **并行分支 A — Contract 起草**（主线程）：
    基于任务类型和探索范围，撰写 Sprint Contract 初稿（3-5 条具体完成标准）
    → 各类型 Contract 要求和示例见 references/contract-examples.md
    将 Contract 写入 $PROJECT_ROOT/_meta/contracts/T-{id}-contract.md

  **并行分支 B — 探索**（Explore subagent x N）：
    → 各类型探索策略和 prompt 模板见 $PROJECT_ROOT/_methodology/07-exploration-strategies.md
    执行前先读取 $PROJECT_ROOT/_meta/source-path-mapping.md 获取探索路径

  等待所有并行分支完成后：
  - 合并所有 Explore agent 的发现
  - 根据深度探索结果修订 Contract（可能发现初稿遗漏的关键机制）
  - 最终 Contract 写入 $PROJECT_ROOT/_meta/contracts/T-{id}-contract.md

STEP 3 — 提取待验证点（Open Questions）

  在合并探索结果时，识别以下类型的待验证点：

  **类型 A — 跨仓库推断**：探索一端时推断了对端行为，但未实际读取对端代码
  **类型 B — 运行时行为**：代码逻辑表明某种行为，但实际效果取决于配置或运行时状态
  **类型 C — 关联系统影响**：当前系统与其他系统的交互点，但未深入追踪对方逻辑
  **类型 D — 历史决策**：代码中看似非常规的设计，无法从当前代码确定原因
    → 类型 D 优先尝试 /git-archaeology 在线解决，仅 git 历史也无法解释时才标注 LOW 置信度

  处理方式：
  FOR 每个待验证点:
    - 仅影响当前文档 → 在文档中标注为 MEDIUM/LOW 置信度
    - 涉及其他系统且可能改变该系统文档的结论 → 创建 verify 任务
    - 本身就是一个值得独立文档的主题 → 创建 create 任务

  将所有待验证点记录在 $PROJECT_ROOT/_meta/contracts/T-{id}-contract.md 的「待验证点」区

STEP 4 — WRITE / IMPROVE

  IF type == "create":
    读取 $PROJECT_ROOT/templates/ 下对应模板，按 $PROJECT_ROOT/CLAUDE.md 全部规范撰写文档
    存入正确的 Diataxis 目录（$PROJECT_ROOT/docs/ 下）
    确定目标读者角色，按角色知识背景调整写作深度
    更新索引（目录索引 + 主索引）
    对待验证点在相关段落标注置信度

  IF type == "improve":
    读取现有文档和 evaluator 反馈（$PROJECT_ROOT/_meta/contracts/T-{id}-contract.md）
    识别 evaluator 标记的最优先改进项（单变量修改原则），仅做定向改进

  IF type == "verify":
    读取原始待验证点描述，用 Explore agent 验证
    验证通过 → 移除置信度标注或升级为 HIGH
    验证失败 → 修正文档中的错误结论
    发现新问题 → 创建新的 verify 或 improve 任务

  → 写作规范见 $PROJECT_ROOT/CLAUDE.md 和 $PROJECT_ROOT/_methodology/03-quality-standards.md
  → 各类型写作要点见 $PROJECT_ROOT/_methodology/03-quality-standards.md

STEP 5 — HANDOFF（读写协议见 $PROJECT_ROOT/_meta/task-schema.md）

  释放 Claim Lock：`python3 .claude/skills/doc-research/scripts/claim-task.py --release T-{id}`
  读取 $PROJECT_ROOT/_meta/task-queue.yaml，更新该任务：
    status: review_pending
    claimed_at: null

  IF STEP 3 产生了跨系统 verify 任务或新 create 任务：
    追加新任务到 $PROJECT_ROOT/_meta/task-queue.yaml 的 tasks 列表
    递增 meta.next_id
    新任务字段：id, priority, type, target, status: pending, score, roles, depends_on, batch, description

  更新 meta.updated_at
  写回 $PROJECT_ROOT/_meta/task-queue.yaml，重新生成 task-queue.md（模板见 $PROJECT_ROOT/_meta/task-schema.md）
  追加 $PROJECT_ROOT/_meta/research-log.md（本次迭代记录）

  后台评估（可选，默认启用）：
    IF prompt 中包含 [--skip-eval]（外部调度器模式）：
      跳过后台 evaluator 启动
      输出摘要：「T-{id} 已完成撰写，状态 review_pending，等待外部调度评估」
    ELSE（正常 session 中手动调用）：
      启动后台 Evaluator subagent（run_in_background=true）：
        使用 general-purpose agent，prompt 包含文档路径、Sprint Contract、评分标准
        输出到 $PROJECT_ROOT/_meta/contracts/T-{id}-contract.md 追加评估记录
        根据评分结果归档或标记 improve
      输出摘要：「T-{id} 已完成撰写，Evaluator 正在后台评估」
```

## 源码路径映射

所有项目特定的源码路径映射存放在 `$PROJECT_ROOT/_meta/source-path-mapping.md`。执行 STEP 2 时读取该文件获取探索路径。

## 日志格式

每次迭代**追加到 `$PROJECT_ROOT/_meta/research-log.md` 的末尾**（使用 `cat >>` 或定位到文件最后一行后追加，禁止插入开头或中间）：

```markdown
### [日期] 迭代 #NNN

- **任务**: T-XXX (目标文件名)
- **动作**: create / improve / verify
- **Sprint Contract**: $PROJECT_ROOT/_meta/contracts/T-XXX-contract.md
- **改进维度**: （仅 improve 时填写，如「evaluator #7 批判性分析」）
- **探索文件**: [列表]
- **关键发现**: [1-2 句]
- **待验证点**: [数量] 个（A 类 x 个 / B 类 x 个 / C 类 x 个 / D 类 x 个）
- **衍生任务**: [新创建的 verify/create 任务 ID 列表，如无则写「无」]
- **状态**: review_pending（等待 /doc-review 评估）
- **下一步**: [建议]
```

## 安全规则

- 单次调用只处理 1 个任务
- **任务认领必须且只能通过 claim-task.py 脚本。禁止任何手动认领、直接写 lock 文件、直接改 YAML status 的行为。脚本失败时必须 STOP，不得降级为手动操作。**
- 不自评打分（由 /doc-review 负责）
- 不删除任何文件
- $PROJECT_ROOT/src/ 目录只读
- 改进时遵循 evaluator 反馈，不自行判断优先级

## Gotchas

- 任务认领 **必须** 通过 `claim-task.py` 脚本执行，绝不手动编辑 lock 文件或 YAML status
- 不要自我评估文档质量，这是 `/doc-review` 的职责
- 执行 STEP 2 前先读取 `$PROJECT_ROOT/_meta/source-path-mapping.md`，不要猜测源码路径
- 写文档前检查是否已有相关的 sys-/how-/ref- 文档，避免与已有文档产生矛盾
