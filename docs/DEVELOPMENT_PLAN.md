# Open-AutoGLM 开发计划

## 项目目标

将 Open-AutoGLM 项目与 Agno 框架集成，在保证数据安全的前提下，增强 Agent 的记忆、知识和协作能力。

---

## 核心架构

### 设计原则

1. **尊重 AutoGLM 特性**：AutoGLM 是端到端的视觉语言模型，同时承担"感知+决策"，不强行拆分
2. **最小改动原则**：保持现有 PhoneAgent 核心逻辑，通过封装和扩展实现增强
3. **数据安全分层**：敏感数据（截屏）保持本地，仅文本信息可选择性传递给云端

### 架构图

```
                              用户指令
                                 │
                                 ▼
              ┌─────────────────────────────────┐
              │      Orchestrator Agent         │  ← 新增：Agno 实现
              │  (任务理解 + 步骤分解 + 调度)     │     可用云端/本地 LLM
              │                                 │
              │  内置能力:                        │
              │  - Memory（用户偏好记忆）         │
              │  - Knowledge（操作知识检索）      │
              └───────────────┬─────────────────┘
                              │ 下发子任务（纯文本）
                              ▼
              ┌─────────────────────────────────┐
              │       StepExecutor Agent        │  ← 现有 PhoneAgent 改造
              │    (原 PhoneAgent，保持核心)      │     本地 AutoGLM
              │                                 │
              │  AutoGLM: 截图 → 思考 → 动作     │
              │  ActionHandler: 执行 ADB        │
              └───────────────┬─────────────────┘
                              │ ADB 命令
                              ▼
                         手机设备
```

### 现有代码映射

| 新架构组件 | 现有模块 | 改动 |
|-----------|----------|------|
| StepExecutor | `phone_agent/agent.py` | 重命名，添加 `execute_subtask()` |
| ActionHandler | `phone_agent/actions/handler.py` | 不变 |
| ADB 操作 | `phone_agent/adb/*` | 不变 |
| ModelClient | `phone_agent/model/client.py` | 不变 |
| Orchestrator | **新增** | Agno Agent |

### 数据安全原则

| 数据类型 | 敏感级别 | 处理策略 |
|----------|----------|----------|
| 屏幕截图 | 🔴 极高 | 仅本地 AutoGLM 处理，永不传输 |
| 点击坐标 | 🔴 高 | 仅本地处理，不暴露给 Orchestrator |
| 应用内容（聊天、账单等） | 🔴 极高 | 仅本地 AutoGLM 分析，分析后丢弃 |
| 当前应用名 | 🟡 中 | 可选择性传递（脱敏后） |
| 任务描述 | 🟢 低 | 可传递给 Orchestrator |
| 执行状态（成功/失败） | 🟢 低 | 可安全传输 |
| 用户偏好（脱敏） | 🟢 低 | 可存储在 Memory 中 |

### 数据安全边界

```
┌─────────────────────────────────────────────────────────────┐
│                    可云端（仅文本）                           │
│                                                             │
│   Orchestrator: 任务理解、规划、Memory、Knowledge            │
│   输入: 用户文本指令                                         │
│   输出: 子任务列表（文本）                                    │
└─────────────────────────────────────────────────────────────┘
                              │ 只传文本
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    必须本地（敏感数据）                        │
│                                                             │
│   StepExecutor: AutoGLM + ADB                              │
│   处理: 截屏、坐标、应用内容                                  │
│   返回: 脱敏的执行状态                                        │
└─────────────────────────────────────────────────────────────┘
```

### 敏感场景处理

对于高敏感场景（银行、支付、隐私应用），系统应：

1. **自动检测**：识别敏感应用（如银行App、支付宝付款页）
2. **跳过云端**：直接使用本地 StepExecutor，不经过 Orchestrator
3. **用户确认**：涉及转账、删除等操作时，强制二次确认（Human-in-the-loop）

### 架构风险与解决方案

| 风险 | 描述 | 解决方案 |
|------|------|----------|
| **Context 丢失** | Orchestrator 看不到截图，只看到 StepExecutor 返回的文本。如果返回描述不准确（如漏掉关键弹窗），上层会"瞎指挥" | 在 `ExecutionResult` 中包含关键 UI 状态（当前 App、页面主要文字、是否有弹窗等） |
| **执行延迟** | 双层架构增加调用链路，可能导致响应变慢 | 简单任务支持直接模式跳过 Orchestrator |
| **状态不同步** | Orchestrator 规划时的状态与实际执行时可能不一致 | StepExecutor 每步执行前重新感知，发现异常及时反馈 |

**ExecutionResult 设计建议**：

```python
@dataclass
class ExecutionResult:
    """StepExecutor 返回给 Orchestrator 的脱敏结果"""
    success: bool                    # 是否成功
    message: str                     # 执行结果描述
    
    # 关键 UI 状态（脱敏但信息充分）
    current_app: str | None          # 当前应用名
    page_summary: str | None         # 页面主要内容摘要
    has_popup: bool                  # 是否有弹窗
    available_actions: list[str]     # 当前可用操作提示
    
    # 控制信息
    needs_user_input: bool           # 是否需要用户介入
    should_retry: bool               # 是否建议重试
```

---

## Phase 1: 基础改造

### 1.1 改造 PhoneAgent 为 StepExecutor

- [ ] 重命名 `PhoneAgent` 为 `StepExecutor`
- [ ] 添加 `execute_subtask(subtask: str)` 方法，接收文本子任务
- [ ] 添加 `ExecutionResult` 返回脱敏结果
- [ ] 保持原有 `run()` 方法兼容，支持直接调用

### 1.2 创建 Orchestrator Agent

- [ ] 基于 Agno Agent 创建 Orchestrator
- [ ] 配置 System Prompt（任务规划专家）
- [ ] 将 StepExecutor 封装为 Agno Tool

### 1.3 添加基础 Memory

- [ ] 配置本地 SQLite 存储
- [ ] 实现用户偏好记忆（如常用联系人、咖啡口味）
- [ ] 测试记忆的自动提取和检索

### 1.4 更新入口

- [ ] 更新 `main.py` 支持两种模式：
  - 直接模式：`--direct` 直接使用 StepExecutor（兼容现有）
  - 编排模式：`--orchestrate` 使用 Orchestrator + StepExecutor

### 交付物

```
phone_agent/
├── agent.py                 # 保留，import StepExecutor 兼容
├── step_executor.py         # 新文件，StepExecutor 类
├── orchestrator/            # 新目录
│   ├── __init__.py
│   ├── agent.py             # Agno Orchestrator
│   ├── tools.py             # StepExecutor Tool 封装
│   └── memory.py            # Memory 配置
├── actions/                 # 不变
├── adb/                     # 不变
├── model/                   # 不变
└── config/                  # 不变
```

---

## Phase 2: 知识增强

### 2.1 构建应用操作知识库

- [ ] 整理主流应用的操作指南（Markdown 格式）
- [ ] 配置 Agno KnowledgeBase（本地文件）
- [ ] 实现知识检索，辅助 Orchestrator 规划

### 2.2 实现 RAG 检索增强

- [ ] 配置本地向量数据库（LanceDB，无需外部服务）
- [ ] 实现操作指南的向量化索引
- [ ] 集成到 Orchestrator 的任务规划流程

### 2.3 添加会话历史记忆

- [ ] 配置会话摘要记忆
- [ ] 实现跨轮次对话的上下文保持
- [ ] 支持追问和任务延续

### 交付物

```
phone_agent/
├── orchestrator/
│   └── knowledge.py         # 知识库配置
├── knowledge/               # 知识库内容
│   ├── apps/               # 各应用操作指南
│   │   ├── wechat.md       # 微信操作指南
│   │   ├── taobao.md       # 淘宝操作指南
│   │   └── ...
│   └── rules/              # 通用操作规则
│       └── common.md       # 通用规则
└── data/
    └── vector_db/          # 本地向量数据库
```

---

## Phase 3: 能力扩展

### 3.1 添加外部工具

- [ ] 集成本地搜索工具（优先 SearXNG 自托管）
- [ ] 添加实用工具（天气、时间、计算器）
- [ ] 确保工具调用不泄露敏感信息

### 3.2 实现 Team 协作模式（可选）

- [ ] 评估是否需要专门化 Agent
- [ ] 如需要，设计 Route 模式的 Team
- [ ] 测试多 Agent 协作效果

### 3.3 部署 AgentOS API

- [ ] 基于 Agno AgentOS 暴露 REST API
- [ ] 实现本地认证机制
- [ ] 编写 API 使用文档

### 交付物

```
phone_agent/
├── orchestrator/
│   ├── tools.py             # 扩展工具集
│   └── team.py              # Team 配置（可选）
├── api/
│   ├── __init__.py
│   ├── server.py            # AgentOS 服务
│   └── auth.py              # 认证模块
└── docs/
    └── API.md               # API 文档
```

---

## Phase 4: 生产化

### 4.1 添加评估系统

- [ ] 定义任务成功率评估指标
- [ ] 编写自动化测试用例
- [ ] 配置 Agno Evals 进行回归测试

### 4.2 实现监控和日志

- [ ] 添加结构化日志（执行步骤、耗时）
- [ ] 实现任务追踪（可回溯）
- [ ] 配置异常告警

### 4.3 多用户支持

- [ ] 实现用户隔离（独立记忆/配置）
- [ ] 添加用户认证
- [ ] 测试多用户并发场景

### 交付物

```
phone_agent/
├── evals/
│   ├── __init__.py
│   ├── test_cases.py        # 测试用例
│   └── metrics.py           # 评估指标
├── monitoring/
│   ├── __init__.py
│   ├── logging.py           # 日志配置
│   └── tracing.py           # 执行追踪
└── auth/
    ├── __init__.py
    └── users.py             # 用户管理
```

---

## 部署模式

### 模式 A: 直接模式（兼容现有）

```bash
python main.py --direct "打开微信"
```

- 直接使用 StepExecutor（原 PhoneAgent）
- 不经过 Orchestrator
- 完全本地，最快速

### 模式 B: 编排模式 - 全本地（最安全）

```bash
python main.py --orchestrate --model local "帮我点杯咖啡"
```

- Orchestrator 使用本地 LLM（Qwen、GLM 等）
- 所有数据不出本地
- 支持 Memory 和 Knowledge

### 模式 C: 编排模式 - 混合部署（推荐）

```bash
python main.py --orchestrate --model gpt-4o-mini "帮我点杯咖啡"
```

- Orchestrator 使用云端 LLM（更强规划能力）
- 仅传递脱敏的任务文本
- 截屏等敏感数据保持本地

### 模式 D: 敏感隔离

- 对银行、支付等高敏感场景
- 自动检测并跳过 Orchestrator
- 直接使用本地 StepExecutor

---

## 开发优先级

| 阶段 | 优先级 | 预估时间 | 核心价值 |
|------|--------|----------|----------|
| Phase 1 | ⭐⭐⭐ | 1-2 周 | 建立双层架构，添加基础记忆 |
| Phase 2 | ⭐⭐⭐ | 1-2 周 | 知识增强，提高任务成功率 |
| Phase 3 | ⭐⭐ | 2-3 周 | 扩展能力，提供 API |
| Phase 4 | ⭐ | 1-2 周 | 生产就绪，多用户支持 |

---

## 下一步行动

1. **Phase 1.1**: 改造 PhoneAgent 为 StepExecutor
   - 添加 `execute_subtask()` 方法
   - 定义 `ExecutionResult` 数据结构
2. **Phase 1.2**: 创建 Orchestrator Agent
   - 配置 Agno Agent
   - 封装 StepExecutor 为 Tool
3. 验证基础架构可行性
