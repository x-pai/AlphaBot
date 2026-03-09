"""
Skill 层：能力单元定义与注册。

当前阶段仅提供静态 Skill 定义（名称、描述、参数模式等），
用于统一给 LLM 暴露工具清单；执行逻辑仍由 AgentService.execute_tool 负责。

后续可在此包内引入：
- Skill Registry：支持按用户 / 环境灰度开启新能力
- Skill Handler：将具体 Service 调用从 AgentService 中拆出，形成独立的可测试单元
"""

