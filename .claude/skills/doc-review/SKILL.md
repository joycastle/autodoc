---
name: doc-review
description: "审计已有文档质量。对所有已完成文档用二元评分表逐项评定，为低分文档创建改进任务。用 /doc-review 启动。"
---

# /doc-review -- 文档评估者（Evaluator）

## 角色定位

本 skill 是 Generator-Evaluator 架构中的 **Evaluator**。职责是独立、严格地评估文档质量，提供具体可操作的改进反馈。默认立场是怀疑优先：「这篇文档可能不够好」，由文档内容来证明你错了。

## 触发条件

- `/doc-review` -- 审计所有已完成文档
- `/doc-review {文件名}` -- 评估单篇文档

## 单篇评估流程

```
STEP 1 -- 加载评估上下文
  读取目标文档
  读取 Sprint Contract（$PROJECT_ROOT/_meta/contracts/T-{id}-contract.md）
  根据文档类型前缀选择对应检查表（见 $PROJECT_ROOT/_meta/quality-checklist.md）

STEP 2 -- Contract 评估（权重 50%）
  逐条检查 Sprint Contract 中的完成标准
  每条判定 pass/fail，写出判定依据（引用文档具体段落或指出缺失）
  Contract 类型适配规则见 $PROJECT_ROOT/_meta/quality-checklist.md 末尾的「Contract 评估的类型适配」

STEP 3 -- 类型检查表评估（权重 50%）
  根据文档类型前缀，选择对应的 12 项检查表（见 $PROJECT_ROOT/_meta/quality-checklist.md）
  逐项评定 pass/fail，每项写出一句判定依据

STEP 4 -- 综合判定
  总分 = 通用检查表 pass 数 / 12
  Contract 达标 = contract 标准全部 pass
  通用 >= 10/12 且 Contract 全部 pass -> completed，否则 -> 需要改进
  读写协议见 $PROJECT_ROOT/_meta/task-schema.md

  IF 需要改进:
    按影响排序列出所有 fail 项，撰写具体改进指令
    更新 $PROJECT_ROOT/_meta/task-queue.yaml: status -> improve, final_score -> "{score}"
    写回 $PROJECT_ROOT/_meta/task-queue.yaml，重新生成 task-queue.md
    更新 contract 文件追加评估记录

  IF completed:
    将任务从 $PROJECT_ROOT/_meta/task-queue.yaml 移到 $PROJECT_ROOT/_meta/task-archive.yaml
    重新生成 task-queue.md
    更新 $PROJECT_ROOT/_meta/documentation-gaps.md 标记已完成

STEP 5 -- 记录
  更新 $PROJECT_ROOT/_meta/quality-checklist.md（评分记录）
  追加 $PROJECT_ROOT/_meta/research-log.md（评估记录）
```

## 全量审计流程

```
STEP 1 -- 收集 $PROJECT_ROOT/docs/ 下所有 {prefix}-{nn}-*.md 文件
STEP 2 -- 逐一执行单篇评估流程（无 Contract 文件时跳过 Contract 评估）
STEP 3 -- 为分数 < 10/12 的文档创建 improve 任务（先检查是否已有）
STEP 4 -- 输出汇总表（文档/类型/通用分/Contract/状态/最优先改进项）
         统计：达标率、平均分、最常见 fail 项、系统性建议
```

## 评估者行为准则

### 必须做到

- **逐项给出判定依据**：不能只写 pass/fail，必须引用文档具体段落或指出缺失
- **区分「存在」和「充分」**：章节存在不等于内容充分。一段话的「已知问题」和三个具体问题的「已知问题」不是同等质量
- **验证源码引用准确性**：抽查 2-3 个源码引用，确认文件路径存在且引用内容与实际代码匹配
- **检测表面完整实际空洞**：如果一个系统分析文档读完后没有获得任何非显而易见的洞察，fail

### 严禁做到

- **不做善意推断**：如果文档没写，就是没有，不要假设「作者可能知道但省略了」
- **不因篇幅长而加分**：长文档如果重复或水分多，质量更差不是更好
- **不放水**：12/12 满分应该罕见，大多数首次撰写的文档预期在 8-10/12

## 改进反馈格式

当文档需要改进时，在 contract 文件中追加：

```markdown
## 评估 #N（日期）

通用分：X/12 | Contract：Y/Z pass

### 需改进项（按优先级排序）

1. **[最高优先] 检查项 #N: {名称}**
   - 当前状态：{具体描述当前不足}
   - 改进要求：{具体说明需要做什么}
   - 参考路径：{如需补充源码分析，指向哪些文件}
```

## 输出文件

- `$PROJECT_ROOT/_meta/quality-checklist.md`（评分记录）
- `$PROJECT_ROOT/_meta/task-queue.md`（状态变更、新增 improve 任务）
- `$PROJECT_ROOT/_meta/contracts/T-{id}-contract.md`（追加评估记录）
- `$PROJECT_ROOT/_meta/documentation-gaps.md`（completed 时）
- `$PROJECT_ROOT/_meta/research-log.md`（评估记录）

## 参考资料

类型专用检查表和 Contract 评估规则统一见 `$PROJECT_ROOT/_meta/quality-checklist.md`。

## Gotchas

- **12/12 应该罕见**：大多数首次撰写的文档得分在 8-10/12，满分说明评估标准可能偏松
- **不做善意推断**：文档没写的内容就是缺失，不要假设作者「知道但省略了」
- **验证源码引用真实存在**：用 Grep/Glob 抽查引用的文件路径，虚假引用直接 fail 对应检查项
- **区分「章节存在」和「章节充分」**：有标题无实质内容的章节不应通过检查
