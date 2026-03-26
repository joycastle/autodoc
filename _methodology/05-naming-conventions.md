# 命名约定

## 文件命名规则

所有文档文件统一使用以下格式：

```
{前缀}-{nn}-{topic}.md
```

- `{前缀}`：两到六个英文小写字母，标识文档类型（见前缀对照表）
- `{nn}`：两位数字序号，从 `01` 开始，同前缀下按逻辑顺序排列
- `{topic}`：小写英文单词，用连字符分隔，简洁描述文档主题

**示例：**

```
arch-01-system-overview.md
arch-02-initialization-flow.md
core-01-game-loop.md
sys-01-network-protocol.md
ref-01-config-fields.md
how-01-add-level-type.md
tut-01-getting-started.md
meta-01-documentation-gaps.md
```

## 前缀对照表

| 前缀 | 文档类型 | Diátaxis 象限 | 存放目录 |
|------|---------|--------------|---------|
| `tut-` | 教程 | Tutorials | `01_tutorials/` |
| `how-` | 操作指南 | How-to Guides | `02_howto/` |
| `ref-` | 参考资料 | Reference | `03_reference/` |
| `arch-` | 架构分析 | Explanation | `04_explanation/` |
| `sys-` | 系统分析 | Explanation | `04_explanation/` |
| `core-` | 核心机制分析 | Explanation | `04_explanation/` |
| `theory-` | 理论建构 | Explanation | `04_explanation/` |
| `meta-` | 元文档 | — | `_meta/` |

**前缀选型指引：**

- `arch-`：适用于跨多个子系统的整体架构文档（如整体架构概览、分层架构、模块依赖图）
- `sys-`：适用于单一系统的深度分析（如存储系统、网络系统、UI 系统）
- `core-`：适用于核心游戏机制的详细分析（如游戏循环、关卡加载、匹配算法）
- `theory-`：适用于设计哲学、模式应用、历史演化等概念性内容

## 目录命名规则

顶层 Diátaxis 目录使用数字前缀保持排序：

```
01_tutorials/
02_howto/
03_reference/
04_explanation/
```

`04_explanation/` 内部允许按系统建立子目录，子目录使用全小写英文加连字符：

```
04_explanation/
├── network-system/
│   ├── sys-01-network-overview.md
│   └── sys-02-protocol-design.md
└── game-core/
    ├── core-01-game-loop.md
    └── core-02-level-loading.md
```

只有当同一系统的文档数量超过 5 份时，才创建子目录。

## 交叉引用格式

文档间互相引用时，使用相对路径：

```markdown
详见 [网络架构概览](../04_explanation/sys-01-network-overview.md)
参考 [配置字段说明](../03_reference/ref-01-config-fields.md)
```

引用源码位置时，使用以下格式：

```markdown
`{SOURCE_ROOT}/Assets/Scripts/Network/NetworkManager.cs:156`
`NetworkManager.Connect()` (`{SOURCE_ROOT}/Assets/Scripts/Network/NetworkManager.cs:156`)
```

其中 `{SOURCE_ROOT}` 是在 `CLAUDE.md` 中定义的源码根路径变量，实际使用时替换为具体路径。

## 章节标题规范

- 使用语义化标题，不使用数字编号（不写「2.1 网络层」，写「网络层」）
- 标题层级最多 4 级（`#` `##` `###` `####`）
- 标题使用中文（技术专有名词可保留英文）
- 顶级标题（`#`）与文件名的 `{topic}` 部分对应

**推荐的通用章节结构（架构/系统分析类）：**

```
# 系统名称

## 系统定位

## 核心组件

## 关键流程

## 设计模式与决策

## 已知问题与风险

## 相关文档
```

## 序号分配策略

同一前缀下，按以下逻辑分配序号：

- `01`：概览或入门（overview / introduction）
- `02`-`09`：核心内容，按逻辑依赖顺序排列（先依赖的排前面）
- `10`+：补充内容、边缘案例、历史记录

序号一旦分配，不随文档内容调整而重新编号（删除文档后，其序号留空，不补位）。
