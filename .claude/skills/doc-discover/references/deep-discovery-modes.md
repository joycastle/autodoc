# 深层知识发现模式（模式 8-13）

本文档包含 doc-discover 深层知识发现模式的详细执行步骤。这些模式从代码级追踪中发现隐性知识缺口，而非目录结构扫描。每个模式使用 Explore subagent 进行源码分析。

使用 `/doc-discover deep` 可一次运行全部深层发现模式。

## 模式 8 — 端到端旅程发现（journeys）

识别跨多个模块的完整用户/系统旅程，这些旅程的知识分散在多篇 sys- 文档中，无人串联。

```
STEP A — 识别旅程入口
  用 Explore agent 扫描以下入口点：

  客户端入口（用户动作触发的旅程）：
    Grep 用户交互触发函数（按项目技术栈调整搜索模式）
    Grep 请求发送函数（API 调用、RPC 请求等）
    每个用户动作触发的请求是一条潜在旅程的起点

  服务端入口（系统事件触发的旅程）：
    Grep 定时任务（cron、scheduler、ticker 等）
    Grep 事件处理（event handler、subscriber 等）
    每个定时任务或事件订阅是一条系统旅程的起点

STEP B — 追踪旅程链路
  FOR 每个高价值入口点（选择涉及核心业务、跨 3+ 模块的）：
    用 Explore agent 从入口开始追踪调用链：
    1. 前端发送了什么请求？
    2. 后端哪个 handler 接收？
    3. handler 调用了哪些其他业务模块？
    4. 是否触发了异步事件？谁在订阅？
    5. 最终数据写入了哪些存储？
    6. 是否有推送/回调通知前端？

  旅程长度 = 跨越的模块数
  IF 旅程长度 >= 3 且无现有 journey- 文档覆盖：
    标记为候选旅程

STEP C — 旅程分类与优先级
  高价值旅程信号：
  - 涉及金钱/支付流转 → P0
  - 核心业务循环 → P0
  - 用户交互链（跨多模块的用户操作流程）→ P1
  - 运营流程链（配置 → 发布 → 生效 → 监控）→ P1
  - 生命周期链（创建 → 活跃 → 过期 → 归档）→ P1

  基于 STEP A/B 的发现，列出候选旅程清单。

  FOR 每个候选旅程:
    创建 create 任务，类型 journey-，优先级按上述信号判定
```

## 模式 9 — 故障与恢复路径发现（failures）

发现代码中的异常处理、重试、降级、恢复机制，这些是线上事故排查的关键知识。

```
STEP A — 扫描故障处理模式
  用 Explore agent 并行搜索以下模式：

  服务端故障处理（src/server/）：
    Grep "retry|Retry|重试" → 重试逻辑
    Grep "fallback|Fallback|降级" → 降级策略
    Grep "recover|Recover|panic" → panic 恢复
    Grep "timeout|Timeout|超时" → 超时处理
    Grep "rollback|Rollback|回滚" → 事务回滚
    Grep "compensat|补偿" → 补偿事务

  客户端故障处理（src/client/）：
    Grep "Reconnect|reconnect|重连" → 断线重连
    Grep "Retry|retry" → 请求重试
    Grep "Cache|cache|缓存" → 离线缓存/降级
    Grep "ErrorHandler|OnError" → 错误处理链

STEP B — 评估故障路径覆盖
  FOR 每个发现的故障处理机制:
    检查所在模块的 sys- 文档是否覆盖了该机制
    覆盖标准：文档中有专门段落分析该故障路径，非一句话提及

  故障路径分类：
  - 网络故障：断连、超时、重连（影响所有客户端系统）
  - 支付故障：支付失败、补单、退款（影响交易系统，P0）
  - 数据故障：数据库写入失败、条件更新冲突（影响数据一致性）
  - 并发故障：竞态条件、死锁、重复请求（影响业务逻辑）
  - 服务故障：微服务不可用、消息丢失（影响服务间通信）

STEP C — 创建任务
  IF 某类故障路径涉及 3+ 模块且无文档覆盖：
    创建 journey- 类型任务（故障旅程也是一种端到端路径）
    标题格式：journey-XX-{故障类型}-recovery
  IF 某模块的故障处理在 sys- 文档中明显不足：
    创建 improve 任务，指明需补充的故障路径
```

## 模式 10 — 隐式耦合分析（coupling）

发现模块间不通过 import 而通过共享资源形成的隐式依赖。

```
STEP A — 共享数据库表/集合
  用 Explore agent 搜索数据表定义和引用（按项目技术栈调整 Grep 模式）：
    构建「表名 → 引用模块」映射
    IF 同一张表被 2+ 个业务模块直接访问：
      标记为隐式耦合点
      文档需求：哪些模块共享该表？读写模式是什么？是否有一致性风险？

STEP B — 共享消息 Topic/Channel
  搜索消息发布和订阅模式（Publish/Subscribe/Emit/On 等）
  构建「topic → 发布者/订阅者」映射
  IF 一个 topic 有 1 个发布者 + 2+ 个订阅者：
    标记为事件扇出耦合
  IF 订阅者依赖发布顺序：
    标记为时序耦合（升级到模式 11）

STEP C — 共享配置键
  搜索配置读取模式（GetConfig/config.Get 等）
  构建「配置项 → 使用模块」映射
  IF 同一配置项被 3+ 模块引用：
    检查是否有隐式约束（模块 A 假设字段 X 的值在某范围内，模块 B 可以修改该值）

STEP D — 共享缓存 Key
  搜索缓存操作模式（redis/cache/memcache 等）
  构建「key pattern → 使用模块」映射

FOR 每个隐式耦合点:
  IF 涉及数据一致性风险 → 创建 theory- 任务（分析耦合模式和风险）
  IF 属于特定旅程的一部分 → 合并到对应 journey- 任务
  IF 仅需在现有文档中补充说明 → 创建 improve 任务
```

## 模式 11 — 时序与并发分析（temporal）

发现系统中对执行顺序、时间窗口、并发控制有隐式依赖的逻辑。可使用 `/git-archaeology` 的 commit pattern 分析辅助发现时序相关的变更集中区。

```
STEP 0 — Git 时序热点（可选，委托 git-archaeology）
  调用 Skill("git-archaeology", args="commit patterns for cron, ticker, schedule, mutex, lock in src/server/")
  识别时序相关代码的变更频率和近期修改趋势
  高频变更的时序代码 → 优先分析（可能是活跃的问题区）

STEP A — 定时任务清单
  Grep "cron|ticker|NewTicker|time\.After|Schedule" in src/server/
  构建定时任务清单：
    - 任务名称
    - 执行频率
    - 涉及的模块
    - 执行时的副作用（写了什么数据、发了什么事件）

  IF 两个定时任务操作同一数据且无显式协调：
    标记为时序风险

STEP B — 业务生命周期时序
  追踪具有生命周期管理的业务实体的状态事件：
    开始 → 进行中 → 结算 → 归档
  IF 多个系统的生命周期事件相互依赖：
    标记为跨系统时序依赖

STEP C — 并发控制机制
  搜索并发控制原语（Lock/Mutex/atomic/CAS/条件更新等）
  分析哪些操作有显式并发保护，哪些没有

STEP D — 消息顺序依赖
  分析异步消息消费是否依赖特定顺序
  IF 存在「必须先处理 A 再处理 B」但无显式保证：
    标记为消息顺序风险

FOR 每个时序发现:
  IF 涉及多个系统的生命周期协调 → 创建 journey- 任务
  IF 是单系统内的并发模式 → 创建 improve 任务（补充到对应 sys-）
  IF 是跨系统的时序模式 → 创建 theory- 任务
```

## 模式 12 — 决策考古（decisions）

从代码和 git 历史中发掘设计决策的背景和原因。本模式充分利用 `/git-archaeology` skill 进行深度历史分析。

```
STEP A — 代码中的决策信号
  Grep "TODO|HACK|FIXME|WORKAROUND|XXX|NOTE:" in src/server/ src/client/
  按模块分组，统计数量
  IF 某模块 TODO/HACK 数量异常高（> 5）：
    标记为技术债集中区，可能需要独立的决策分析文档

STEP B — 非常规设计模式
  用 Explore agent 阅读已有 sys- 文档中「已知问题与风险」章节
  提取其中提到但未深入分析的设计选择
  常见信号：
  - 「硬编码了 X，原因未知」
  - 「使用了非标准做法 X」
  - 「性能优化导致了 X 复杂性」

STEP C — Git 历史深度分析（委托 git-archaeology）
  调用 Skill("git-archaeology") 执行以下分析：

  1. **重构里程碑**：识别大规模重构 commit（大量文件删除/重命名），
     提取 commit message 中的设计意图
  2. **模块演化时间线**：追踪关键业务模块的创建时间和重大变更节点
  3. **决策信号 commit**：搜索 commit message 含 "refactor|重构|migrate|迁移|
     deprecated|废弃|replace|替换" 的 commit，分析决策背景
  4. **贡献者集中度**：识别特定模块的主要贡献者，
     作为后续决策验证的访谈线索

  将 git-archaeology 的输出与 STEP A/B 的发现交叉比对：
  - 代码中的 HACK 注释 + git blame 对应 commit → 可追溯决策时间和背景
  - 文档中的「原因未知」 + git log --follow → 可追溯演化路径

FOR 每个决策发现:
  IF 是跨模块的架构决策 → 创建 arch- 任务（架构决策记录 ADR）
  IF 是单模块的非常规设计 → 创建 improve 任务（补充到对应 sys-）
  IF 是历史演化过程 → 评估是否值得独立文档
```

## 模式 13 — 运维暗知识发现（tribal）

发现那些只存在于运维经验中、代码中有迹可循的操作性知识。

```
STEP A — 部署约束
  分析部署脚本和 CI/CD 配置（路径从 $PROJECT_ROOT/_meta/source-path-mapping.md 获取）：
    - 是否有显式的部署顺序依赖？（剧本 A 必须在 B 之前）
    - 是否有环境特殊处理？（prod 与 test 的配置差异）
    - 是否有回滚脚本？覆盖了哪些服务？

STEP B — 容量与限流配置
  Grep "rateLimit|RateLimit|限流|throttle" in src/server/
  Grep "maxConn|MaxConnection|pool.*size|capacity" in src/server/ src/configs/
  构建「服务 → 容量限制」映射
  IF 容量限制未在任何文档中提及 → 标记为暗知识

STEP C — 监控与告警定义
  搜索监控和运维目录（路径从 $PROJECT_ROOT/_meta/source-path-mapping.md 获取）
  提取：
  - 监控指标名称和含义
  - 告警阈值和触发条件
  - 告警响应建议（如果代码中有注释）

STEP D — 错误码与排查映射
  Grep "ErrCode|ErrorCode|错误码" in src/server/ src/proto/
  构建「错误码 → 含义 → 常见原因」映射
  IF 错误码清单未在 ref- 文档中覆盖 → 标记为缺口

STEP E — 数据迁移与兼容性
  Grep "migrate|Migration|兼容|compat|legacy|旧版" in src/server/
  识别向后兼容处理逻辑
  IF 存在活跃的兼容层但无文档说明何时可移除 → 标记为暗知识

FOR 每个运维暗知识发现:
  按类型创建任务：
  - 部署约束/容量限制 → how- 任务（运维操作类）
  - 监控指标/错误码 → ref- 任务（参考资料类）
  - 兼容性逻辑 → improve 任务（补充到对应 sys-）
```
