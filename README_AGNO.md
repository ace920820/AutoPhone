# Agno 编排 Agent

这个分支引入了基于 [Agno](https://github.com/agno-agi/agno) 框架的编排 Agent，位于 `agno_agent` 分支。

## 功能介绍

编排 Agent (Orchestrator) 作为一个智能中枢，负责接收用户的复杂指令，进行任务规划和拆解，并指挥底层的 AutoGLM Phone Agent 执行具体的操作。

**主要特性：**
- **任务规划**：将复杂任务（如跨应用操作）拆解为多个简单的子任务。
- **自我修正**：根据每一步的执行结果调整后续计划。
- **状态保持**：在多步操作中保持对任务上下文的理解。

## 环境准备

除了主项目的依赖外，还需要安装 agno：

```bash
pip install -r requirements.txt
```

确保你设置了 OpenAI API Key（用于编排 Agent 的大脑）：

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."

# Linux/macOS
export OPENAI_API_KEY="sk-..."
```

## 使用方法

### 命令行启动

使用新的入口脚本 `orchestrator_main.py`：

```bash
# 交互模式
python orchestrator_main.py

# 执行特定任务
python orchestrator_main.py "在小红书找一家好吃的火锅店，然后去大众点评看评分"
```

### Web 界面启动

启动 Web 界面以获得更友好的交互体验：

```bash
python orchestrator_main.py --web
```

访问 `http://localhost:8000` 即可使用。

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--web` | 启动 Web 界面 | `False` |
| `--model-id` | 编排 Agent 使用的模型 (OpenAI/DashScope) | `gpt-4o` / `qwen-plus` |
| `--phone-base-url` | Phone Agent 模型服务 URL | `http://localhost:8000/v1` |
| `--phone-model` | Phone Agent 模型名称 | `autoglm-phone-9b` |
| `--device-id` | 指定 ADB 设备 ID | (自动检测) |

### 代码结构

- `phone_agent/orchestrator.py`: 定义编排 Agent，配置 Prompt 和工具。
- `phone_agent/tools.py`: 封装 `AutoGLMTools`，将 Phone Agent 的能力暴露给 Agno。
- `orchestrator_main.py`: 程序的启动入口。

## 示例流程

1. **用户输入**: "帮我看看最近有什么好看的科幻电影，然后去豆瓣查一下评分"
2. **Orchestrator**: 
   - 思考: 需要先去视频APP或浏览器搜索电影，然后去豆瓣查评分。
   - **Step 1**: 调用 `run_phone_task("打开浏览器搜索最近上映的科幻电影")`
3. **Phone Agent**: 执行操作并返回结果（如"搜索到了《沙丘2》..."）。
4. **Orchestrator**:
   - 思考: 知道了电影名是《沙丘2》，下一步去豆瓣。
   - **Step 2**: 调用 `run_phone_task("打开豆瓣搜索沙丘2并查看评分")`
5. **Phone Agent**: 执行操作并返回结果（如"评分8.3..."）。
6. **Orchestrator**: 汇总信息，向用户回复最终结果。
