# 流式反馈和查询接口详解

## 问题背景

你提出了一个很好的问题：
> "目前我也可以在控制台日志中实时看到 phone_agent 的思考和操作，为什么要加流式反馈呢？查询接口的作用是什么？"

让我详细解释这两个功能的实际价值和使用场景。

---

## 一、流式反馈 vs 控制台日志

### 当前情况的问题

虽然你现在可以在控制台看到日志，但存在以下问题：

#### 1. **Orchestrator 看不到执行过程** ⚠️

```python
# 当前实现
def run_phone_task(self, task_description: str) -> str:
    result = self.phone_agent.run(task_description)  # 阻塞调用
    return result  # 只返回最终结果字符串
```

**问题**：
- Orchestrator 调用 `run_phone_task` 后，会**阻塞等待**直到任务完成
- Orchestrator **完全不知道** PhoneAgent 正在做什么
- 只能得到最终的字符串结果："任务完成" 或 "任务失败"

**场景示例**：

```
用户: "在小红书找火锅店，然后去大众点评看评分，最后用微信分享"

Orchestrator 思考: 好的，我先让 PhoneAgent 去小红书找火锅店
Orchestrator 调用: run_phone_task("在小红书搜索火锅店")

[等待中... 30秒过去了...]
[等待中... 60秒过去了...]  ← Orchestrator 不知道发生了什么
[等待中... 90秒过去了...]

PhoneAgent 返回: "已在小红书找到火锅店：海底捞"

Orchestrator: 好的，现在去大众点评...
```

在这 90 秒里，Orchestrator **完全不知道**：
- PhoneAgent 是否卡住了？
- 执行到第几步了？
- 是否遇到了问题？
- 是否需要调整策略？

#### 2. **无法动态调整策略** ⚠️

假设 PhoneAgent 在执行过程中发现：
- 小红书没有搜索到结果
- 应用崩溃了
- 网络超时了

**当前情况**：Orchestrator 只能等到最后才知道失败，无法中途介入。

**理想情况**：Orchestrator 实时知道进度，可以动态调整：

```python
# 流式反馈示例
async def run_phone_task_with_feedback(task: str):
    async for step_info in phone_agent.run_streaming(task):
        print(f"步骤 {step_info.step}: {step_info.action}")
        
        # Orchestrator 可以根据进度做决策
        if step_info.action == "搜索无结果":
            # 动态调整策略
            return "小红书没找到，让我换大众点评试试"
        
        if step_info.step > 20:
            # 任务太复杂，分解为更小的子任务
            return "任务太复杂，需要重新规划"
```

#### 3. **Web 界面无法显示进度** ⚠️

控制台日志只能在命令行看到，但如果你有 Web 界面：

```
当前 Web 界面:
┌─────────────────────────────┐
│ 正在执行任务...              │
│ [转圈圈...]                  │  ← 用户只能干等
└─────────────────────────────┘

有流式反馈的 Web 界面:
┌─────────────────────────────┐
│ 正在执行任务...              │
│ ✓ 步骤 1: 打开小红书         │
│ ✓ 步骤 2: 点击搜索框         │
│ ⏳ 步骤 3: 输入"火锅店"...   │  ← 用户知道进度
│ 进度: 3/10 步                │
└─────────────────────────────┘
```

---

## 二、流式反馈的实现和价值

### 实现方式

```python
# phone_agent/tools.py (增强版)
class AutoGLMTools(Toolkit):
    
    def run_phone_task(
        self, 
        task_description: str,
        callback: Optional[Callable[[Dict], None]] = None  # 新增回调
    ) -> str:
        """
        执行任务，支持流式反馈
        
        callback 会在每个步骤后被调用，让 Orchestrator 知道进度
        """
        self.phone_agent.reset()
        
        # 设置步骤回调
        def step_callback(step_info):
            if callback:
                # 将步骤信息传递给 Orchestrator
                callback({
                    "step": step_info.step_count,
                    "action": step_info.action,
                    "thinking": step_info.thinking,
                    "success": step_info.success,
                    "current_app": step_info.current_app
                })
        
        self.phone_agent.set_step_callback(step_callback)
        return self.phone_agent.run(task_description)
```

### 使用场景

#### 场景 1：实时进度显示

```python
# orchestrator 使用
def execute_complex_task(task: str):
    progress_info = []
    
    def on_step(step_info):
        progress_info.append(step_info)
        print(f"[进度] 步骤 {step_info['step']}: {step_info['action']}")
        
        # 发送到 Web 前端
        websocket.send(json.dumps(step_info))
    
    result = tools.run_phone_task(task, callback=on_step)
    return result, progress_info
```

#### 场景 2：智能超时处理

```python
def execute_with_timeout(task: str, max_steps: int = 20):
    step_count = 0
    
    def on_step(step_info):
        nonlocal step_count
        step_count += 1
        
        if step_count > max_steps:
            # 任务太复杂，提前终止
            phone_agent.stop()
            raise TimeoutError("任务步骤过多，需要重新规划")
    
    return tools.run_phone_task(task, callback=on_step)
```

#### 场景 3：动态策略调整

```python
def smart_execute(task: str):
    failed_attempts = 0
    
    def on_step(step_info):
        nonlocal failed_attempts
        
        if not step_info['success']:
            failed_attempts += 1
            
            if failed_attempts >= 3:
                # 连续失败 3 次，切换策略
                phone_agent.pause()
                print("检测到连续失败，尝试替代方案...")
                # 调整策略后继续
                phone_agent.resume()
    
    return tools.run_phone_task(task, callback=on_step)
```

---

## 三、查询接口的作用

### 问题：为什么需要查询接口？

当前 Orchestrator 只能通过 `run_phone_task` 来**执行任务**，但无法**查询状态**。

### 实际场景

#### 场景 1：任务执行前的状态检查

```python
# 没有查询接口
orchestrator: "去小红书搜索火锅店"
phone_agent: [开始执行] → 发现小红书没安装 → 失败

# 有查询接口
orchestrator: "去小红书搜索火锅店"
orchestrator: 先查询一下手机状态...
status = tools.get_phone_status()
# {
#   "current_app": "桌面",
#   "installed_apps": ["微信", "抖音", "淘宝"],  # 没有小红书！
#   "network": "已连接",
#   "battery": 85
# }
orchestrator: "检测到没有小红书，改用大众点评"
```

#### 场景 2：多步骤任务的中间状态查询

```python
# 复杂任务：在小红书找火锅店，记录店名，然后去大众点评搜索

# 步骤 1
orchestrator: run_phone_task("在小红书搜索火锅店")
result: "已找到火锅店"

# 问题：找到的是哪家店？店名是什么？
# 当前只能得到字符串 "已找到火锅店"，没有结构化信息

# 有查询接口
orchestrator: run_phone_task("在小红书搜索火锅店")
result: "已找到火锅店"

# 查询屏幕信息
screen_info = tools.extract_screen_info("提取当前屏幕上的店名和评分")
# {
#   "店名": "海底捞火锅(王府井店)",
#   "评分": "4.8",
#   "人均": "150元"
# }

# 步骤 2：使用提取的信息
orchestrator: run_phone_task(f"打开大众点评搜索{screen_info['店名']}")
```

#### 场景 3：异常情况的诊断

```python
# 任务执行失败
orchestrator: run_phone_task("发送微信消息给张三")
result: "任务失败"

# 问题：为什么失败？是网络问题？应用崩溃？找不到联系人？
# 当前只能得到 "任务失败"，无法诊断原因

# 有查询接口
orchestrator: run_phone_task("发送微信消息给张三")
result: "任务失败"

# 查询详细状态
status = tools.get_phone_status()
# {
#   "current_app": "桌面",  # 微信退出了
#   "last_error": "应用崩溃",
#   "screenshot": "..."
# }

orchestrator: "检测到微信崩溃，重新启动微信后再试"
```

#### 场景 4：信息提取（不执行操作）

```python
# 只想获取信息，不想执行操作

# 没有查询接口：必须执行任务
orchestrator: run_phone_task("打开淘宝，告诉我首页有什么商品")
# 问题：会真的打开淘宝，改变了手机状态

# 有查询接口：只查询不操作
orchestrator: 
  1. 先查询当前状态
  status = tools.get_phone_status()
  
  2. 如果已经在淘宝首页，直接提取信息
  if status['current_app'] == '淘宝':
      info = tools.extract_screen_info("提取首页商品列表")
  else:
      # 需要打开淘宝
      run_phone_task("打开淘宝")
      info = tools.extract_screen_info("提取首页商品列表")
```

---

## 四、完整的增强工具调用实现

```python
# phone_agent/tools.py (完整增强版)
class AutoGLMTools(Toolkit):
    
    def __init__(self, ...):
        super().__init__(name="autoglm_tools")
        self.phone_agent = PhoneAgent(...)
        
        # 注册多个工具
        self.register(self.run_phone_task)
        self.register(self.get_phone_status)          # 查询状态
        self.register(self.extract_screen_info)       # 提取信息
        self.register(self.check_app_installed)       # 检查应用
        self.register(self.pause_phone_task)          # 暂停任务
        self.register(self.resume_phone_task)         # 恢复任务
    
    def run_phone_task(
        self, 
        task_description: str,
        callback: Optional[Callable] = None
    ) -> str:
        """执行任务（带流式反馈）"""
        # ... 实现 ...
    
    def get_phone_status(self) -> str:
        """
        获取当前手机状态
        
        返回 JSON 字符串，包含：
        - current_app: 当前应用
        - step_count: 执行步数
        - last_action: 最后一个操作
        - is_busy: 是否正在执行任务
        """
        from phone_agent.adb import get_current_app
        
        state = {
            "current_app": get_current_app(self.phone_agent.agent_config.device_id),
            "step_count": self.phone_agent.step_count,
            "is_busy": self.phone_agent._step_count > 0,
            "device_id": self.phone_agent.agent_config.device_id
        }
        
        return json.dumps(state, ensure_ascii=False)
    
    def extract_screen_info(self, query: str) -> str:
        """
        从当前屏幕提取信息（不执行操作）
        
        Args:
            query: 要提取的信息，例如 "提取店名和评分"
        
        Returns:
            提取的结构化信息（JSON 字符串）
        """
        from phone_agent.adb import get_screenshot
        
        screenshot = get_screenshot(self.phone_agent.agent_config.device_id)
        
        # 使用 VLM 提取信息
        messages = [
            {"role": "system", "content": "你是信息提取专家，从屏幕截图中提取结构化数据，返回 JSON 格式。"},
            {"role": "user", "content": [
                {"type": "text", "text": query},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{screenshot.base64_data}"
                }}
            ]}
        ]
        
        response = self.phone_agent.model_client.request(messages)
        return response
    
    def check_app_installed(self, app_name: str) -> str:
        """
        检查应用是否已安装
        
        Args:
            app_name: 应用名称，例如 "小红书"
        
        Returns:
            "已安装" 或 "未安装"
        """
        from phone_agent.config.apps import APP_PACKAGE_MAP
        from phone_agent.adb import check_app_installed
        
        package_name = APP_PACKAGE_MAP.get(app_name)
        if not package_name:
            return f"未知应用: {app_name}"
        
        installed = check_app_installed(
            package_name,
            self.phone_agent.agent_config.device_id
        )
        
        return "已安装" if installed else "未安装"
```

---

## 五、对比总结

### 当前实现 vs 增强实现

| 功能 | 当前实现 | 增强实现 | 价值 |
|------|---------|---------|------|
| **执行任务** | ✅ 支持 | ✅ 支持 | 基础功能 |
| **查看日志** | ✅ 控制台 | ✅ 控制台 + 回调 | 日志可见性 |
| **实时进度** | ❌ Orchestrator 看不到 | ✅ 流式反馈 | **关键改进** |
| **状态查询** | ❌ 不支持 | ✅ get_phone_status | **关键改进** |
| **信息提取** | ❌ 必须执行任务 | ✅ extract_screen_info | **关键改进** |
| **动态调整** | ❌ 无法中途介入 | ✅ 可暂停/恢复 | 灵活性 |
| **Web 界面** | ❌ 无进度显示 | ✅ 实时进度条 | 用户体验 |
| **错误诊断** | ❌ 只知道失败 | ✅ 详细状态 | 可调试性 |

---

## 六、实际使用示例

### 示例 1：智能任务执行

```python
# Orchestrator 的智能决策
async def smart_task_execution(task: str):
    # 1. 先检查状态
    status = json.loads(tools.get_phone_status())
    print(f"当前应用: {status['current_app']}")
    
    # 2. 检查应用是否安装
    if "小红书" in task:
        installed = tools.check_app_installed("小红书")
        if installed == "未安装":
            return "小红书未安装，无法执行任务"
    
    # 3. 执行任务（带进度反馈）
    progress = []
    def on_progress(step_info):
        progress.append(step_info)
        print(f"进度: {len(progress)}/50")
        
        # 如果步骤太多，提前终止
        if len(progress) > 30:
            raise Exception("任务过于复杂，需要分解")
    
    result = tools.run_phone_task(task, callback=on_progress)
    
    # 4. 提取结果信息
    if "搜索" in task:
        info = tools.extract_screen_info("提取搜索结果")
        return f"{result}\n详细信息: {info}"
    
    return result
```

### 示例 2：多步骤任务协调

```python
# 复杂任务：比价
async def compare_prices(product: str):
    results = {}
    
    # 步骤 1：在淘宝搜索
    tools.run_phone_task(f"打开淘宝搜索{product}")
    taobao_info = tools.extract_screen_info("提取商品价格")
    results['淘宝'] = json.loads(taobao_info)
    
    # 步骤 2：在京东搜索
    tools.run_phone_task(f"打开京东搜索{product}")
    jd_info = tools.extract_screen_info("提取商品价格")
    results['京东'] = json.loads(jd_info)
    
    # 步骤 3：比较价格
    return f"价格对比: {json.dumps(results, ensure_ascii=False)}"
```

---

## 七、结论

### 流式反馈的价值

1. ✅ **让 Orchestrator 知道执行进度**（而不是盲等）
2. ✅ **支持动态策略调整**（根据中间结果改变计划）
3. ✅ **改善用户体验**（Web 界面显示进度）
4. ✅ **提前发现问题**（不用等到最后才知道失败）

### 查询接口的价值

1. ✅ **任务前检查**（避免执行注定失败的任务）
2. ✅ **信息提取**（获取数据而不改变状态）
3. ✅ **错误诊断**（了解失败原因）
4. ✅ **状态感知**（Orchestrator 知道手机当前状态）

### 核心区别

**控制台日志**：给人看的，Orchestrator 看不到
**流式反馈**：给 Orchestrator 看的，让 AI 能做出智能决策

这就是为什么即使有控制台日志，仍然需要流式反馈和查询接口！
