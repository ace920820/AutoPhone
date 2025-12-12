"""
Phone Agent 执行跟踪模块。

提供任务执行过程的详细记录和可视化功能：
- 记录每个步骤的截图、操作和结果
- 生成 HTML 可视化报告
- 支持 JSON 格式导出
- 便于调试和问题排查
"""

import base64
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

from phone_agent.logging_config import get_logger

# 获取日志器
logger = get_logger("tracing")

# ============================================================
# 跟踪数据目录
# ============================================================
TRACE_DIR = "traces"
os.makedirs(TRACE_DIR, exist_ok=True)


# ============================================================
# 数据类定义
# ============================================================
@dataclass
class StepTrace:
    """
    单个执行步骤的跟踪记录。
    """
    step_number: int
    timestamp: str
    current_app: str
    screenshot_base64: Optional[str] = None
    thinking: str = ""
    action: dict = field(default_factory=dict)
    action_result: str = ""
    success: bool = True
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典（不含截图以减小体积）"""
        data = asdict(self)
        # 截图单独处理，这里只保留标记
        data['has_screenshot'] = self.screenshot_base64 is not None
        data.pop('screenshot_base64', None)
        return data


@dataclass
class TaskTrace:
    """
    完整任务的跟踪记录。
    """
    trace_id: str
    task_description: str
    start_time: str
    end_time: Optional[str] = None
    status: str = "running"  # running, completed, failed
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    steps: list[StepTrace] = field(default_factory=list)
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['steps'] = [step.to_dict() for step in self.steps]
        return data


# ============================================================
# 执行跟踪器
# ============================================================
class ExecutionTracer:
    """
    执行跟踪器类。
    
    负责记录任务执行过程中的每个步骤，包括截图、操作、结果等。
    支持生成 HTML 报告和 JSON 导出。
    
    Example:
        >>> tracer = ExecutionTracer("搜索火锅店")
        >>> tracer.start()
        >>> tracer.add_step(screenshot, "小红书", "搜索火锅", {"action": "Type"}, "成功")
        >>> tracer.finish("任务完成")
        >>> tracer.save_html_report()
    """
    
    def __init__(self, task_description: str, metadata: dict = None):
        """
        初始化跟踪器。
        
        Args:
            task_description: 任务描述
            metadata: 额外的元数据（如设备ID、模型名称等）
        """
        self.trace = TaskTrace(
            trace_id=str(uuid.uuid4())[:8],
            task_description=task_description,
            start_time=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        self._step_start_time: Optional[datetime] = None
        self._screenshots: dict[int, str] = {}  # 步骤号 -> base64截图
        
        logger.info(f"创建执行跟踪: {self.trace.trace_id} - {task_description}")
    
    def start(self) -> None:
        """开始跟踪"""
        self.trace.status = "running"
        self.trace.start_time = datetime.now().isoformat()
        logger.info(f"开始任务跟踪: {self.trace.trace_id}")
    
    def add_step(
        self,
        screenshot_base64: Optional[str],
        current_app: str,
        thinking: str,
        action: dict,
        action_result: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        添加一个执行步骤的记录。
        
        Args:
            screenshot_base64: 截图的 base64 编码
            current_app: 当前应用名称
            thinking: AI 的思考过程
            action: 执行的操作
            action_result: 操作结果
            success: 是否成功
            error_message: 错误信息（如果有）
        """
        step_number = len(self.trace.steps) + 1
        
        # 计算步骤耗时
        now = datetime.now()
        duration_ms = 0.0
        if self._step_start_time:
            duration_ms = (now - self._step_start_time).total_seconds() * 1000
        self._step_start_time = now
        
        # 创建步骤记录
        step = StepTrace(
            step_number=step_number,
            timestamp=now.isoformat(),
            current_app=current_app,
            screenshot_base64=screenshot_base64,
            thinking=thinking,
            action=action,
            action_result=action_result,
            success=success,
            duration_ms=duration_ms,
            error_message=error_message
        )
        
        # 保存截图引用
        if screenshot_base64:
            self._screenshots[step_number] = screenshot_base64
        
        self.trace.steps.append(step)
        self.trace.total_steps = step_number
        
        if success:
            self.trace.successful_steps += 1
        else:
            self.trace.failed_steps += 1
        
        # 记录日志
        action_name = action.get('action', 'unknown')
        logger.debug(
            f"步骤 {step_number}: {action_name} @ {current_app} - "
            f"{'成功' if success else '失败'} ({duration_ms:.0f}ms)"
        )
    
    def finish(self, result: str, success: bool = True) -> None:
        """
        完成任务跟踪。
        
        Args:
            result: 最终结果
            success: 任务是否成功
        """
        self.trace.end_time = datetime.now().isoformat()
        self.trace.status = "completed" if success else "failed"
        self.trace.final_result = result
        
        logger.info(
            f"任务跟踪完成: {self.trace.trace_id} - "
            f"状态: {self.trace.status}, "
            f"步骤: {self.trace.total_steps}, "
            f"成功: {self.trace.successful_steps}, "
            f"失败: {self.trace.failed_steps}"
        )
    
    def fail(self, error_message: str) -> None:
        """
        标记任务失败。
        
        Args:
            error_message: 错误信息
        """
        self.trace.end_time = datetime.now().isoformat()
        self.trace.status = "failed"
        self.trace.error_message = error_message
        
        logger.error(f"任务跟踪失败: {self.trace.trace_id} - {error_message}")
    
    def save_json(self, include_screenshots: bool = False) -> str:
        """
        保存为 JSON 文件。
        
        Args:
            include_screenshots: 是否包含截图数据
            
        Returns:
            保存的文件路径
        """
        filename = f"trace_{self.trace.trace_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(TRACE_DIR, filename)
        
        data = self.trace.to_dict()
        
        # 如果需要包含截图
        if include_screenshots:
            data['screenshots'] = self._screenshots
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存 JSON 跟踪报告: {filepath}")
        return filepath
    
    def save_html_report(self) -> str:
        """
        生成并保存 HTML 可视化报告。
        
        Returns:
            保存的文件路径
        """
        filename = f"trace_{self.trace.trace_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(TRACE_DIR, filename)
        
        html_content = self._generate_html_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"保存 HTML 跟踪报告: {filepath}")
        return filepath
    
    def _generate_html_report(self) -> str:
        """生成 HTML 报告内容"""
        
        # 生成步骤卡片
        steps_html = ""
        for step in self.trace.steps:
            screenshot_html = ""
            if step.step_number in self._screenshots:
                screenshot_html = f'''
                <div class="screenshot">
                    <img src="data:image/png;base64,{self._screenshots[step.step_number]}" 
                         alt="Step {step.step_number} Screenshot" 
                         onclick="this.classList.toggle('expanded')">
                </div>
                '''
            
            status_class = "success" if step.success else "error"
            action_json = json.dumps(step.action, ensure_ascii=False, indent=2)
            
            steps_html += f'''
            <div class="step-card {status_class}">
                <div class="step-header">
                    <span class="step-number">步骤 {step.step_number}</span>
                    <span class="step-app">{step.current_app}</span>
                    <span class="step-time">{step.duration_ms:.0f}ms</span>
                    <span class="step-status {'✅' if step.success else '❌'}">{
                        '成功' if step.success else '失败'
                    }</span>
                </div>
                {screenshot_html}
                <div class="step-content">
                    <div class="thinking">
                        <h4>💭 思考过程</h4>
                        <pre>{step.thinking}</pre>
                    </div>
                    <div class="action">
                        <h4>🎯 执行操作</h4>
                        <pre>{action_json}</pre>
                    </div>
                    <div class="result">
                        <h4>📋 执行结果</h4>
                        <p>{step.action_result}</p>
                    </div>
                    {f'<div class="error"><h4>❌ 错误信息</h4><p>{step.error_message}</p></div>' 
                     if step.error_message else ''}
                </div>
            </div>
            '''
        
        # 计算执行时间
        try:
            start = datetime.fromisoformat(self.trace.start_time)
            end = datetime.fromisoformat(self.trace.end_time) if self.trace.end_time else datetime.now()
            duration = (end - start).total_seconds()
            duration_str = f"{duration:.1f}秒"
        except:
            duration_str = "未知"
        
        # 完整 HTML
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>任务执行报告 - {self.trace.trace_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: rgba(255,255,255,0.95);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            color: #1a1a2e;
            font-size: 24px;
            margin-bottom: 16px;
        }}
        .header .task-desc {{
            color: #4a4a6a;
            font-size: 16px;
            padding: 12px;
            background: #f5f5f7;
            border-radius: 8px;
            margin-bottom: 16px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
        }}
        .stat-item {{
            text-align: center;
            padding: 12px;
            background: #f5f5f7;
            border-radius: 8px;
        }}
        .stat-item .value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-item .label {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}
        .stat-item.success .value {{ color: #10b981; }}
        .stat-item.error .value {{ color: #ef4444; }}
        
        .steps {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .step-card {{
            background: rgba(255,255,255,0.95);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .step-card.error {{
            border-left: 4px solid #ef4444;
        }}
        .step-card.success {{
            border-left: 4px solid #10b981;
        }}
        .step-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 16px;
            background: #f8f9fa;
            border-bottom: 1px solid #eee;
        }}
        .step-number {{
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        }}
        .step-app {{
            background: #e0e7ff;
            color: #4338ca;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 13px;
        }}
        .step-time {{
            color: #666;
            font-size: 13px;
            margin-left: auto;
        }}
        .step-status {{
            font-size: 14px;
        }}
        .screenshot {{
            padding: 16px;
            background: #1a1a2e;
            text-align: center;
        }}
        .screenshot img {{
            max-width: 300px;
            max-height: 400px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .screenshot img:hover {{
            transform: scale(1.02);
        }}
        .screenshot img.expanded {{
            max-width: 100%;
            max-height: none;
        }}
        .step-content {{
            padding: 16px;
        }}
        .step-content h4 {{
            color: #1a1a2e;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .step-content pre {{
            background: #f5f5f7;
            padding: 12px;
            border-radius: 8px;
            font-size: 13px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .step-content p {{
            color: #4a4a6a;
            font-size: 14px;
        }}
        .thinking, .action, .result, .error {{
            margin-bottom: 16px;
        }}
        .error {{
            background: #fef2f2;
            padding: 12px;
            border-radius: 8px;
        }}
        .error h4 {{
            color: #dc2626;
        }}
        .error p {{
            color: #991b1b;
        }}
        
        .footer {{
            text-align: center;
            color: white;
            padding: 20px;
            font-size: 13px;
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 任务执行报告</h1>
            <div class="task-desc">
                <strong>任务:</strong> {self.trace.task_description}
            </div>
            <div class="stats">
                <div class="stat-item">
                    <div class="value">{self.trace.trace_id}</div>
                    <div class="label">跟踪 ID</div>
                </div>
                <div class="stat-item">
                    <div class="value">{self.trace.total_steps}</div>
                    <div class="label">总步骤</div>
                </div>
                <div class="stat-item success">
                    <div class="value">{self.trace.successful_steps}</div>
                    <div class="label">成功</div>
                </div>
                <div class="stat-item error">
                    <div class="value">{self.trace.failed_steps}</div>
                    <div class="label">失败</div>
                </div>
                <div class="stat-item">
                    <div class="value">{duration_str}</div>
                    <div class="label">耗时</div>
                </div>
                <div class="stat-item {'success' if self.trace.status == 'completed' else 'error'}">
                    <div class="value">{'✅' if self.trace.status == 'completed' else '❌'}</div>
                    <div class="label">{self.trace.status}</div>
                </div>
            </div>
        </div>
        
        <div class="steps">
            {steps_html}
        </div>
        
        <div class="footer">
            生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Phone Agent Execution Tracer
        </div>
    </div>
</body>
</html>'''
        
        return html
    
    @property
    def trace_id(self) -> str:
        """获取跟踪 ID"""
        return self.trace.trace_id


# ============================================================
# 全局跟踪器管理
# ============================================================
_current_tracer: Optional[ExecutionTracer] = None


def start_trace(task_description: str, metadata: dict = None) -> ExecutionTracer:
    """
    开始一个新的任务跟踪。
    
    Args:
        task_description: 任务描述
        metadata: 额外元数据
        
    Returns:
        跟踪器实例
    """
    global _current_tracer
    _current_tracer = ExecutionTracer(task_description, metadata)
    _current_tracer.start()
    return _current_tracer


def get_current_tracer() -> Optional[ExecutionTracer]:
    """获取当前活跃的跟踪器"""
    return _current_tracer


def end_trace(result: str = None, success: bool = True, save_report: bool = True) -> Optional[str]:
    """
    结束当前任务跟踪。
    
    Args:
        result: 最终结果
        success: 是否成功
        save_report: 是否保存报告
        
    Returns:
        HTML 报告路径（如果保存）
    """
    global _current_tracer
    if _current_tracer is None:
        return None
    
    _current_tracer.finish(result or "任务完成", success)
    
    report_path = None
    if save_report:
        report_path = _current_tracer.save_html_report()
        _current_tracer.save_json()
    
    _current_tracer = None
    return report_path
