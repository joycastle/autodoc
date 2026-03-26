---
name: doc-discover
description: "文档健康监测与深层知识发现：模块缺口、源码漂移、类型失衡、横切主题、角色视角、端到端旅程、故障路径、隐式耦合、时序分析、决策考古、运维暗知识。用 /doc-discover 启动。"
---

# /doc-discover — 文档健康监测

文档体系的自动化健康检查工具，通过 13 种检测模式发现文档缺口、内容漂移和隐性知识需求，产出结构化任务进入 task-queue.yaml。

## 触发条件

用户输入 `/doc-discover` 或要求「查找文档缺口」「检查文档健康度」「发现新文档需求」。

支持参数：
- `/doc-discover` — 运行全部检测模式
- `/doc-discover modules` — 仅模块扫描
- `/doc-discover drift` — 仅漂移检测
- `/doc-discover balance` — 仅类型平衡分析
- `/doc-discover themes` — 仅横切主题发现
- `/doc-discover depth` — 仅深度审查
- `/doc-discover personas` — 仅角色视角分析
- `/doc-discover verify` — 仅待验证点汇总
- `/doc-discover journeys` — 仅端到端旅程发现
- `/doc-discover failures` — 仅故障与恢复路径发现
- `/doc-discover coupling` — 仅隐式耦合分析
- `/doc-discover temporal` — 仅时序与并发分析
- `/doc-discover decisions` — 仅决策考古
- `/doc-discover tribal` — 仅运维暗知识发现
- `/doc-discover deep` — 运行所有深层发现模式（8-13）

## 总体流程

```
STEP 0 — 建立基线
  读取 $PROJECT_ROOT/_meta/documentation-gaps.md、$PROJECT_ROOT/_meta/task-queue.yaml
  读取 $PROJECT_ROOT/docs/ 下所有已有文档的 YAML frontmatter 或首行标题
  构建「文档 → 源码模块」映射（从 doc-research 的 $PROJECT_ROOT/_meta/source-path-mapping.md 获取）

STEP 1-13 — 按需执行各检测模式（见下方模式总览表）

STEP FINAL — 汇总报告
  打印健康度仪表盘（见 references/output-format.md）
  将新发现的任务写入 $PROJECT_ROOT/_meta/task-queue.yaml（读写协议见 $PROJECT_ROOT/_meta/task-schema.md，写入后须重新生成 task-queue.md）
  追加记录到 $PROJECT_ROOT/_meta/research-log.md
```

## 模式总览

### 基础检测（模式 1-7）

详细步骤见 `references/basic-modes.md`。

| 模式 | 参数 | 说明 |
|------|------|------|
| 1 — 模块扫描 | `modules` | 检测源码中未被文档覆盖的新增模块 |
| 2 — 漂移检测 | `drift` | 检测文档写成后源码是否发生显著变更 |
| 3 — 类型平衡 | `balance` | 检测 Diataxis 四象限文档分布是否合理 |
| 4 — 横切主题 | `themes` | 识别跨模块反复出现的设计模式或架构主题 |
| 5 — 深度审查 | `depth` | 检测文档深度是否匹配源码模块规模 |
| 6 — 角色视角 | `personas` | 从不同角色视角审视文档缺口 |
| 7 — 待验证点 | `verify` | 汇总文档中的低置信度待验证点 |

### 深层发现（模式 8-13）

详细步骤见 `references/deep-discovery-modes.md`。

| 模式 | 参数 | 说明 |
|------|------|------|
| 8 — 端到端旅程 | `journeys` | 识别跨多模块的完整用户/系统旅程 |
| 9 — 故障路径 | `failures` | 发现异常处理、重试、降级、恢复机制 |
| 10 — 隐式耦合 | `coupling` | 发现通过共享资源形成的模块间隐式依赖 |
| 11 — 时序并发 | `temporal` | 发现执行顺序、时间窗口、并发控制的隐式依赖 |
| 12 — 决策考古 | `decisions` | 从代码和 git 历史发掘设计决策的背景 |
| 13 — 运维暗知识 | `tribal` | 发现只存在于运维经验中的操作性知识 |

### 辅助参考

- 任务优先级和文档类型判定规则：`$PROJECT_ROOT/_methodology/06-priority-and-types.md`
- 报告输出格式模板：`references/output-format.md`

## 与其他 skill 的协作

- **doc-research**：doc-discover 产出的任务进入 task-queue.yaml（读写协议见 $PROJECT_ROOT/_meta/task-schema.md），由 doc-research 认领执行
- **doc-review**：漂移检测发现的 improve 任务，doc-research 改进后由 doc-review 评估
- **调用频率**：建议每周运行一次全量检测，或在已知有大量源码变更后运行 drift 模式

## 常见陷阱

**必须先读取源码路径映射**：不要直接扫描 `$PROJECT_ROOT/src/` 目录结构。所有源码路径必须从 `$PROJECT_ROOT/_meta/source-path-mapping.md` 读取，该文件定义了项目特有的目录布局和模块划分规则。直接扫描会遗漏非标准路径或误判目录层级。

**避免创建重复任务**：创建任何新任务前，必须先检查 `$PROJECT_ROOT/_meta/task-queue.yaml` 中是否已存在覆盖相同模块或主题的任务（包括 pending、in-progress、done 状态）。重复任务会造成 doc-research worker 的浪费。

**区分 doc-discover 与 doc-expert 职责**：doc-discover 负责发现缺口和产出任务；doc-expert 负责文档库的战略评审和优先级调整。不要在 discover 流程中做战略层面的取舍判断，也不要在 expert 评审中执行缺口扫描逻辑。
