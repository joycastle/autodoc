# CLAUDE.md

本仓库是 **autodoc** -- 一套基于 Claude Code 的自动化文档生成框架，可应用于任何软件项目。

## 项目定位

autodoc 提供：
- 文档方法论（Diataxis 框架、提取工作流、质量标准）
- 文档生成 Skill 套件（discover / expert / research / review / mermaid-lint）
- 多 worker 并行编排脚本（autodoc.py）
- 任务队列协议与质量评分体系
- 各文档类型模板

框架本身不包含任何特定项目的文档内容或源码引用。使用时需在目标项目中配置 CLAUDE.md 指定源码路径、角色定义等项目特有信息。

## 目录结构

```
autodoc/
├── CLAUDE.md                           # 本文件
├── autodoc.py                          # 多 worker TUI 编排器
├── _methodology/                       # 文档方法论（项目可定制）
│   ├── 01-diataxis-framework.md
│   ├── 02-extraction-workflow.md
│   ├── 03-quality-standards.md
│   ├── 04-research-planning.md
│   ├── 05-naming-conventions.md
│   ├── 06-priority-and-types.md
│   └── 07-exploration-strategies.md
├── templates/                          # 各类型文档模板
├── _meta/                              # 协议与标准（项目可定制）
│   ├── quality-checklist.md            #   二元评分表 + Contract 规则
│   ├── task-schema.md                  #   任务队列 YAML Schema
│   └── source-path-mapping.template.md #   源码路径映射模板
└── .claude/skills/                     # Skill 套件（框架核心）
    ├── doc-discover/                   #   文档健康监测
    ├── doc-expert/                     #   文档库战略评审
    ├── doc-research/                   #   自主研究循环（含脚本）
    ├── doc-review/                     #   质量审计与评分
    └── mermaid-lint/                   #   Mermaid 图表校验
```

## 写作规范

- 所有文档正文使用中文，代码标识符保留英文原名
- 禁止在 Markdown 中使用 emoji
- 不在章节之间添加 `---` 水平线
- 标题层级最多 4 级，不使用数字编号标题

## 文件命名约定

文档文件统一使用 `{前缀}-{nn}-{topic}.md` 格式，`nn` 为两位序号。

| 前缀 | 类型 |
|------|------|
| `tut-` | 教程 |
| `how-` | 操作指南 |
| `ref-` | 参考资料 |
| `arch-` | 架构分析 |
| `sys-` | 系统分析 |
| `core-` | 核心机制分析 |
| `theory-` | 理论建构 |
| `journey-` | 端到端旅程 |

## 代码比例上限

| 文档类型 | 代码比例上限 | 单个代码块行数上限 |
|---------|------------|-----------------|
| 教程 | 20% | 15 行 |
| 操作指南 | 15% | 15 行 |
| 参考资料 | 10% | 15 行 |
| 架构分析 | 10% | 10 行 |
| 系统分析 | 15% | 15 行 |
| 理论建构 | 5% | 10 行 |
| 端到端旅程 | 10% | 10 行 |

## Mermaid 图表规范

- 序列图：最多 6 个参与者，15 个步骤
- 流程图：最多 15 个节点
- 类图：最多 8 个类
- 每个文档最多 3 个 Mermaid 图表
- 图表必须配有中文说明段落
- 图表中的换行使用 `<br>`，禁止使用 `\n`

## 任务认领规则

`/doc-research` 的任务认领**必须且只能**通过 `python3 .claude/skills/doc-research/scripts/claim-task.py` 脚本执行。该脚本使用 `flock` 全局互斥锁防止并行争抢。禁止以任何理由绕过脚本手动认领任务。

## 变更记录

对 `_methodology/`、`.claude/skills/`、`templates/`、`_meta/quality-checklist.md` 的修改须在使用项目的 `_meta/research-log.md` 末尾追加变更记录。
