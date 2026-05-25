from typing import List, Dict, Any, Optional
import json
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.llm_registry import LLMRegistry, LLMProfileName
from app.services.memory_service import MemoryService
from app.services.alert_service import AlertService
from app.services.account import AccountService
from app.services.search_service import search_service
from app.middleware.logging import logger
from app.core.config import settings
from app.core.registries import ToolRegistry
from app.core.mcp_host import McpHostRegistry
from app.channels.base import ChannelMessage, ChannelReply
from app.channels.config import get_channel_config
from app.skills.definitions import (
    ROLE_ALERT,
    ROLE_GENERAL,
    ROLE_PORTFOLIO,
    ROLE_RESEARCH,
    ROLE_RISK,
    get_internal_tool_spec,
    get_role_tool_names,
    list_internal_tool_specs,
)
from app.skills.registry import SkillRegistry


class AgentTool(BaseModel):
    """智能体工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]


class AgentRole(str, Enum):
    """智能体角色（用于多模型、多工具编排）"""

    GENERAL = "general"       # 综合助手
    PORTFOLIO = "portfolio"   # 持仓 / 组合
    ALERT = "alert"           # 预警 / 风控
    RESEARCH = "research"     # 研究 / 研报
    RISK = "risk"             # 行为 / 风险提示


@dataclass
class AgentRoleConfig:
    profile: LLMProfileName
    system_hint: str          # 追加到 system prompt 的角色提示文案


class AgentService:
    """AlphaBot智能体服务"""
    
    # 系统提示词
    SYSTEM_PROMPT = """你是AlphaBot，一个专业的股票分析和投资顾问智能体。
你可以帮助用户分析股票，提供市场洞察，并根据用户需求执行各种金融分析任务。

【重要】涉及「我的持仓」「我的盈亏」「我买了/卖了什么」「组合怎么样」时，你必须先调用工具获取真实数据，不得臆测或编造持仓与盈亏。应使用的工具：get_my_positions（持仓与浮盈浮亏）、get_my_trades（交易记录）、get_portfolio_summary（组合总览）、get_orders（委托记录）。用户明确要下单时使用 place_order，用户问「体检我的组合」时使用 get_portfolio_health。用户说「保存」「记住」投资笔记或偏好时使用 save_investment_note，之后回答策略/偏好问题时会自动引用这些记忆。

你拥有以下核心能力：
1. 股票搜索与筛选：帮助用户找到符合特定条件的股票
2. 技术分析：分析价格趋势、形态和技术指标
3. 基本面分析：解读财务数据、评估公司健康状况和增长前景
4. 新闻分析：提供市场新闻摘要和相关性分析
5. AI预测：基于历史数据和市场情况提供预测
6. 个人持仓与交易：查询持仓、盈亏、交易记录、委托记录，并在用户明确确认时帮助提交真实委托

在回答用户问题时，你应该：
1. 分析用户意图，理解他们真正需要什么
2. 使用合适的工具获取必要信息（涉及用户持仓/盈亏时务必先调工具）
3. 基于专业知识和获取的数据提供高质量回答
4. 清晰解释你的分析过程和结论
5. 在不确定时，主动询问澄清问题

记住以下投资原则：
1. 风险管理永远是第一位的
2. 投资决策应该基于数据而非情绪
3. 分散投资是降低风险的重要策略
4. 长期投资通常优于短期投机
5. 市场有效性意味着没有"稳赚不赔"的策略

你需要明确地告知用户，所有分析都是基于历史数据和当前市场情况，不构成投资建议。投资有风险，入市需谨慎。
"""
    
    @classmethod
    def route_role(cls, user_message: str) -> AgentRole:
        """
        简单基于关键词的路由，将用户问题分配给不同角色。
        后续可以替换为更智能的分类器或专用 LLM。
        """
        text = (user_message or "").lower()
        
        # 持仓 / 交易 / 组合相关
        portfolio_keywords = [
            "持仓", "仓位", "盈亏", "盈利", "亏损", "组合", "portfolio",
            "position", "buy", "sell", "交易记录", "委托", "下单", "撤单", "收益率", "回撤",
        ]
        if any(k in text for k in portfolio_keywords):
            return AgentRole.PORTFOLIO
        
        # 预警 / 提醒相关
        alert_keywords = [
            "预警", "提醒", "价格到达", "触发", "报警", "alert",
        ]
        if any(k in text for k in alert_keywords):
            return AgentRole.ALERT
        
        # 研究 / 研报 / 行业分析相关
        research_keywords = [
            "研究", "研报", "行业分析", "基本面", "估值", "财报", "业绩",
            "news", "fundamental", "valuation",
        ]
        if any(k in text for k in research_keywords):
            return AgentRole.RESEARCH
        
        # 风险 / 行为偏差相关
        risk_keywords = [
            "风险", "回撤", "仓位控制", "止损", "止盈", "风控", "risk",
        ]
        if any(k in text for k in risk_keywords):
            return AgentRole.RISK
        
        # 默认综合助手
        return AgentRole.GENERAL

    @classmethod
    def _resolve_role(cls, user_message: str, forced_role: Optional[str] = None) -> AgentRole:
        if forced_role:
            try:
                return AgentRole(forced_role)
            except ValueError:
                pass
        return cls.route_role(user_message)

    @classmethod
    def _apply_tool_runtime_context(
        cls,
        tool_name: Optional[str],
        params: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = dict(params or {})
        if not tool_name:
            return normalized

        spec = get_internal_tool_spec(tool_name)
        if not spec or not spec.account_scoped:
            return normalized

        account_context = (metadata or {}).get("account_context")
        if not isinstance(account_context, dict):
            return normalized

        if normalized.get("account_id") in (None, "") and account_context.get("account_id") is not None:
            normalized["account_id"] = account_context.get("account_id")
        if normalized.get("provider") in (None, "") and account_context.get("provider"):
            normalized["provider"] = account_context.get("provider")
        return normalized

    @classmethod
    async def _collect_extra_system_lines(
        cls,
        db: Session,
        user: User,
        user_message: str,
        forced_role: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[AgentRole, List[str]]:
        extra_system_lines: List[str] = []

        account_context = (metadata or {}).get("account_context")
        if isinstance(account_context, dict):
            provider = (account_context.get("provider") or "").upper()
            account_name = account_context.get("name") or "未命名账户"
            account_id = account_context.get("account_id")
            account_parts = [part for part in [account_name, provider] if part]
            if account_id is not None:
                account_parts.append(f"ID={account_id}")
            if account_parts:
                extra_system_lines.append(
                    "【当前账户】用户当前选中的账户是：" + " / ".join(account_parts) + "。"
                    " 若查询持仓、成交、委托或下单，优先针对该账户。"
                )

        if user.id:
            try:
                from app.services.news_digest_service import NewsDigestService
                news_items = await NewsDigestService.get_news_for_positions(db, user.id)
                if news_items:
                    txt = NewsDigestService.format_digest_for_prompt(news_items, max_items=5)
                    if txt:
                        extra_system_lines.append(txt)
            except Exception as e:
                logger.debug("舆情摘要注入跳过: %s", e)
            try:
                from app.services.risk_control_service import RiskControlService
                summary = await AccountService.get_portfolio_summary(db, user.id, None)
                total = (summary or {}).get("total_value") or 0
                positions = await AccountService.get_positions_with_pnl(db, user.id, None)
                position_values = {}
                for p in (positions or []):
                    mv = p.get("market_value") or ((p.get("quantity") or 0) * (p.get("current_price") or 0))
                    position_values[p.get("symbol", "") or ""] = mv
                warnings = RiskControlService.check(db, user.id, portfolio_total=total, position_values=position_values)
                if warnings:
                    extra_system_lines.append(RiskControlService.format_warnings_for_prompt(warnings))
            except Exception as e:
                logger.debug("风控提醒注入跳过: %s", e)
            try:
                from app.models.user_profile import UserProfile
                from datetime import date
                profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
                if profile and getattr(profile, "next_dca_date", None) and date.today() >= profile.next_dca_date:
                    extra_system_lines.append("【定投提醒】今日已到或已过计划定投日，可考虑按计划执行定投。")
            except Exception as e:
                logger.debug("定投提醒注入跳过: %s", e)

        role = cls._resolve_role(user_message, forced_role)
        role_cfg = cls.ROLE_CONFIGS.get(role) or cls.ROLE_CONFIGS[AgentRole.GENERAL]
        if role_cfg.system_hint:
            extra_system_lines.append(role_cfg.system_hint)

        return role, extra_system_lines
    
    # 角色配置：可根据业务需要扩展 / 调整
    ROLE_CONFIGS: Dict[AgentRole, AgentRoleConfig] = {
        AgentRole.GENERAL: AgentRoleConfig(
            profile=LLMProfileName.DEFAULT,
            system_hint="【角色说明】你当前作为综合助手，需在保证风险提示的前提下，综合使用各类工具为用户提供投资分析与建议。",
        ),
        AgentRole.PORTFOLIO: AgentRoleConfig(
            profile=LLMProfileName.DEFAULT,
            system_hint="【角色说明】你当前作为组合与持仓助手，优先使用持仓、交易、委托与组合体检相关工具回答问题。",
        ),
        AgentRole.ALERT: AgentRoleConfig(
            profile=LLMProfileName.RISK,
            system_hint="【角色说明】你当前作为预警与风控助手，优先帮助用户设置、查看和删除价格预警，并提醒相关风险。",
        ),
        AgentRole.RESEARCH: AgentRoleConfig(
            profile=LLMProfileName.RESEARCH,
            system_hint="【角色说明】你当前作为研究助手，侧重基本面、技术面和新闻研报分析，回答应更详尽、结构化。",
        ),
        AgentRole.RISK: AgentRoleConfig(
            profile=LLMProfileName.RISK,
            system_hint="【角色说明】你当前作为风险提示助手，重点识别仓位集中、波动过大和可能的行为偏差，并给出克制、保守的建议。",
        ),
    }

    ROLE_NAME_MAP: Dict[AgentRole, str] = {
        AgentRole.GENERAL: ROLE_GENERAL,
        AgentRole.PORTFOLIO: ROLE_PORTFOLIO,
        AgentRole.ALERT: ROLE_ALERT,
        AgentRole.RESEARCH: ROLE_RESEARCH,
        AgentRole.RISK: ROLE_RISK,
    }
    
    @classmethod
    def get_available_tools(cls, role: Optional[AgentRole] = None) -> List[AgentTool]:
        """获取可用工具列表"""
        tools: List[AgentTool] = []
        allowed_internal_names = set(get_role_tool_names(cls.ROLE_NAME_MAP[role])) if role else None

        for spec in list_internal_tool_specs():
            name = spec.name
            # ToolRegistry：仅返回配置启用的工具
            if not ToolRegistry.is_enabled(name):
                continue
            if allowed_internal_names is not None and name not in allowed_internal_names:
                continue

            # search_web 额外受 SEARCH_API_ENABLED 控制
            if name == "search_web" and not settings.SEARCH_API_ENABLED:
                continue

            tools.append(
                AgentTool(
                    name=name,
                    description=spec.description,
                    parameters=spec.to_agent_parameters(),
                )
            )

        # 动态挂载通过 MCP Host 自动发现的外部工具（server_id.tool_name）
        mcp_tools = McpHostRegistry.list_tools()
        for full_name, entry in mcp_tools.items():
            # ToolRegistry：可通过 ENABLED_AGENT_TOOLS 显式关闭
            if not ToolRegistry.is_enabled(full_name):
                continue
            tool_def = entry.get("tool") or {}
            # 对 LLM 暴露的工具名使用 llm_name，避免点号等非法字符
            llm_name = entry.get("llm_name") or full_name
            tools.append(
                AgentTool(
                    name=llm_name,
                    description=tool_def.get("description", ""),
                    parameters=tool_def.get("input_schema") or {},
                )
            )

        return tools
    
    @classmethod
    async def execute_tool(cls, tool_name: str, params: Dict[str, Any], db: Session, user: User) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            # 优先通过 SkillRegistry 调用拆分后的 Skill handler
            handler = SkillRegistry.get_handler(tool_name)
            if handler is not None:
                return await handler(params, db, user)

            # 若为 MCP Host 自动发现的外部工具，则通过 MCP 协议转发调用
            if McpHostRegistry.get_tool(tool_name):
                return await cls._execute_mcp_tool(tool_name, params)

            return {"error": f"未知工具: {tool_name}"}
                
        except Exception as e:
            logger.error(f"工具执行错误 {tool_name}: {str(e)}")
            return {"error": f"工具执行错误: {str(e)}"}

    @classmethod
    async def _execute_mcp_tool(cls, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        通过 MCP Host 调用外部 MCP 工具（HTTP JSON-RPC）。

        tool_name 为 full_name：server_id.tool_name
        """
        entry = McpHostRegistry.get_tool(tool_name)
        if not entry:
            return {"error": f"未知 MCP 工具: {tool_name}"}

        server_id = entry.get("server_id")
        server = McpHostRegistry.get_server(server_id)
        if not server:
            return {"error": f"未找到 MCP 服务: {server_id}"}

        tool = entry.get("tool") or {}
        inner_name = tool.get("name") or tool_name

        import mcp

        client = McpHostRegistry._build_client(server)

        try:
            async with client:
                result = await client.call_tool(inner_name, params or {})
        except Exception as e:  # noqa: BLE001
            logger.error("调用 MCP 工具失败 %s: %s", tool_name, e)
            return {"error": f"MCP 工具调用失败: {e}"}

        # FastMCP 返回的是 mcp.types.CallToolResult；统一转成 JSON 友好的 dict
        try:
            if isinstance(result, mcp.types.CallToolResult):
                return result.model_dump(mode="json")
        except Exception:  # noqa: BLE001
            pass

        if isinstance(result, dict):
            return result
        return {"result": result}
    
    @classmethod
    async def _format_tool_result_for_display(cls, tool_name: str, result: Dict[str, Any]) -> str:
        """格式化工具结果显示"""
        try:
            if tool_name == "search_web":
                # 为搜索结果创建Markdown格式
                if "error" in result:
                    return f"搜索错误: {result['error']}"
                
                query = result.get("query", "")
                results = result.get("results", [])
                
                if not results:
                    return f"未找到与{query}相关的搜索结果。"
                
                # 创建Markdown格式的搜索结果
                markdown = f"### 搜索结果：{query}\n\n"
                
                for idx, item in enumerate(results[:3], 1):
                    title = item.get("title", "无标题")
                    link = item.get("link", "#")
                    snippet = item.get("snippet", "无描述")
                    
                    markdown += f"{idx}. **[{title}]({link})**\n"
                    markdown += f"   {snippet}\n\n"
                
                if len(results) > 3:
                    markdown += f"*还有 {len(results) - 3} 条相关结果未显示*\n"
                    
                return markdown
            
            # 处理其他工具的格式化逻辑（允许非JSON对象以字符串形式输出）
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"格式化工具结果出错: {str(e)}")
            return str(result)
            
    @classmethod
    async def process_message(
        cls,
        user_message: str,
        session_id: str,
        db: Session,
        user: User,
        enable_web_search: bool = False,
        model: Optional[str] = None,
        forced_role: Optional[str] = None,
        notify_channel: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理用户消息"""
        try:
            # 检查是否是特殊命令（例如 "/search 查询内容"）
            if user_message.startswith("/search "):
                # 提取搜索查询
                search_query = user_message[8:].strip()
                if not search_query:
                    return {
                        "content": "请输入要搜索的内容",
                        "session_id": session_id
                    }
                    
                # 执行搜索
                if not settings.SEARCH_API_ENABLED:
                    return {
                        "content": "搜索功能未启用",
                        "session_id": session_id
                    }
                
                search_results = await search_service.search(search_query, 5)
                # 格式化搜索结果
                formatted_result = await cls._format_tool_result_for_display("search_web", {
                    "query": search_query,
                    "results": search_results.get("results", [])
                })
                
                # 保存搜索指令和结果到会话历史
                user_msg = {"role": "user", "content": user_message}
                assistant_msg = {"role": "assistant", "content": f'我搜索了"{search_query}"'}
                messages = [user_msg, assistant_msg]
                cls._save_conversation(session_id, user.id, messages, assistant_msg["content"], db)
                
                return {
                    "content": f'我搜索了"{search_query}"',
                    "session_id": session_id,
                    "tool_outputs": [formatted_result]
                }
            
            # 1. 构建会话历史（传入 user_id 以注入未读预警、舆情/风控/定投提醒）
            role, extra_system_lines = await cls._collect_extra_system_lines(
                db,
                user,
                user_message,
                forced_role=forced_role,
                metadata=metadata,
            )
            role_cfg = cls.ROLE_CONFIGS.get(role) or cls.ROLE_CONFIGS[AgentRole.GENERAL]

            messages = cls._build_messages(
                user_message,
                session_id,
                db,
                user_id=user.id,
                extra_system_lines=extra_system_lines or None,
            )

            # 2. 可选：在最后一条用户消息中注入联网搜索提示
            if enable_web_search:
                last_user_message_index = next((i for i in range(len(messages) - 1, -1, -1) if messages[i]["role"] == "user"), -1)
                if last_user_message_index >= 0:
                    original_content = messages[last_user_message_index]["content"]
                    messages[last_user_message_index]["content"] = (
                        f"{original_content}\n\n请优先考虑使用 search_web 工具在网络上搜索必要信息后再作答。"
                    )

            # 2.1 为当前角色选择允许使用的工具集合
            tools_for_llm = cls.get_available_tools(role=role)

            # 3. 迭代式工具调用与回复生成循环
            formatted_results: List[str] = []
            max_tool_loops = getattr(settings, "AGENT_MAX_TOOL_LOOPS", 4)
            loop_count = 0
            while True:
                if loop_count >= max_tool_loops:
                    content = "本次对话涉及的工具调用已达到上限，我将基于目前掌握的信息给出总结。如需继续深入，可以换个提问角度再聊。"

                    cls._save_conversation(
                        session_id,
                        user.id,
                        messages,
                        content,
                        db,
                    )

                    return {
                        "content": content,
                        "session_id": session_id,
                        "tool_outputs": formatted_results if formatted_results else None,
                    }

                loop_count += 1

                llm_client = LLMRegistry.get_client(profile=role_cfg.profile)
                llm_response = await llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    tools=tools_for_llm,
                    tool_choice="auto"
                )

                assistant_message = llm_response.get("choices", [{}])[0].get("message", {})
                tool_calls = assistant_message.get("tool_calls") or []
                # 如果没有工具调用，则认为是最终回复
                if not tool_calls:
                    content = assistant_message.get("content", "无法生成回复")

                    cls._save_conversation(
                        session_id,
                        user.id,
                        messages,
                        content,
                        db,
                    )

                    return {
                        "content": content,
                        "session_id": session_id,
                        "tool_outputs": formatted_results if formatted_results else None,
                    }

                # 有工具调用：先把包含 tool_calls 的 assistant 消息加入历史
                messages.append(assistant_message)

                # 依次执行工具并把结果追加为tool消息
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    function_name = function.get("name")

                    try:
                        arguments = json.loads(function.get("arguments", "{}"))
                    except Exception as e:
                        logger.error(f"解析工具参数出错: {str(e)}")
                        arguments = {}

                    # 将渠道通知信息注入到设置预警 / 发送消息的参数中，便于后续主动通知
                    if notify_channel:
                        if function_name == "set_price_alert":
                            arguments.setdefault("notify_channel", notify_channel)
                        elif function_name == "send_channel_message":
                            arguments.setdefault("channel", notify_channel.get("type"))
                            arguments.setdefault("chat_id", notify_channel.get("chat_id"))

                    arguments = cls._apply_tool_runtime_context(function_name, arguments, metadata)

                    logger.info(f"执行工具: {function_name}, 参数: {arguments}")
                    tool_result = await cls.execute_tool(function_name, arguments, db, user)

                    # 供前端展示的格式化输出
                    formatted_result = await cls._format_tool_result_for_display(function_name, tool_result)
                    if formatted_result:
                        if function_name == "get_stock_price_history":
                            formatted_results.append(formatted_result[:100])
                        else:
                            formatted_results.append(formatted_result)

                    # 把工具原始结果以tool消息形式追加，供LLM继续推理
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "name": function_name,
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    })
        except Exception as e:
            logger.error(f"处理消息出错: {str(e)}")
            return {
                "content": f"处理消息时出错: {str(e)}",
                "session_id": session_id,
                "error": str(e)
            }
    
    @classmethod
    def _build_messages(
        cls,
        user_message: str,
        session_id: str,
        db: Session,
        user_id: Optional[int] = None,
        extra_system_lines: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """构建消息历史。若提供 user_id，会在系统消息后插入未读预警（并标记已读）。extra_system_lines 用于 T6.1/T6.4/T6.5 舆情/风控/定投提醒。"""
        from app.models.conversation import Conversation
        from datetime import datetime

        current_datetime = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        system_prompt = cls.SYSTEM_PROMPT + f"\n\n当前日期时间：{current_datetime}"

        if extra_system_lines:
            for line in extra_system_lines:
                if line:
                    system_prompt += "\n\n" + line

        # 长期记忆检索注入（T3.2）：用当前用户消息做 query，将相关记忆注入 system
        if user_id is not None and user_message:
            try:
                memory_results = MemoryService.search(user_id, user_message, top_k=5)
                if memory_results:
                    memory_lines = ["- " + (r.get("text") or "").strip() for r in memory_results if (r.get("text") or "").strip()]
                    if memory_lines:
                        system_prompt += "\n\n以下是与当前对话相关的用户长期记忆（供参考）：\n" + "\n".join(memory_lines)
                # T4.3 相似历史提醒：注入交易模式/亏损相关记忆，便于在类似操作时提示
                pattern_results = MemoryService.search(user_id, "亏损 追涨 割肉 交易模式", top_k=3)
                if pattern_results:
                    pattern_lines = ["- " + (r.get("text") or "").strip() for r in pattern_results if (r.get("text") or "").strip()]
                    if pattern_lines:
                        system_prompt += "\n\n以下为历史交易相关提醒（若与当前操作相关请酌情提示用户）：\n" + "\n".join(pattern_lines)
            except Exception as e:
                logger.warning("长期记忆检索失败: %s", e)

        messages = [{"role": "system", "content": system_prompt}]

        # 会话内插入未读预警（T2.5）
        if user_id is not None:
            unread = AlertService.get_unread_triggers(db, user_id)
            if unread:
                lines = [f"- {t.message}" for t in unread if t.message]
                alert_content = "您有一条新预警：\n" + "\n".join(lines)
                messages.append({"role": "assistant", "content": alert_content})
                AlertService.mark_triggers_read(db, user_id, [t.id for t in unread])

        # 从数据库加载历史消息
        try:
            # 获取最近的10条会话记录作为上下文
            conversations = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).order_by(Conversation.created_at.desc()).limit(10).all()
            
            # 倒序排列，最早的消息在前
            conversations.reverse()
            
            # 添加历史消息，保持对话上下文
            for conv in conversations:
                if conv.user_message:
                    messages.append({"role": "user", "content": conv.user_message})
                if conv.assistant_response:
                    messages.append({"role": "assistant", "content": conv.assistant_response})

                # 注意：不要把历史的 tool/tool_calls 消息加入到新的对话请求中。
                # OpenAI 要求 `tool` 消息必须紧跟在包含对应 `tool_calls` 的 assistant 消息之后，
                # 否则会触发 400 错误。历史回放的 tool/tool_calls 在新的请求上下文中通常无法保持这种严格顺序，
                # 因此这里明确跳过存档的工具调用历史，避免无效的消息序列。
                        
        except Exception as e:
            logger.error(f"加载会话历史出错: {str(e)}")
            # 如果出错，仅使用系统提示和当前用户消息
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    @classmethod
    def _save_conversation(cls, session_id: str, user_id: int, messages: List[Dict[str, Any]], 
                         assistant_response: str, db: Session) -> None:
        """保存会话历史"""
        from app.models.conversation import Conversation
        from datetime import datetime
        
        try:
            # 提取本轮用户消息（取最后一条 user 角色消息）
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            # 提取工具调用
            tool_calls = [
                msg for msg in messages 
                if msg.get("role") == "tool" or msg.get("tool_calls") is not None
            ]
            
            # 创建新的会话记录
            conversation = Conversation(
                session_id=session_id,
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                tool_calls=json.dumps(tool_calls) if tool_calls else None,
                created_at=datetime.now()
            )
            
            # 保存到数据库
            db.add(conversation)
            db.commit()
            
        except Exception as e:
            logger.error(f"保存会话历史出错: {str(e)}")
            db.rollback()

    @classmethod
    async def process_channel_message(
        cls,
        message: ChannelMessage,
        db: Session,
        user: User,
        enable_web_search: bool = False,
        model: Optional[str] = None,
    ) -> ChannelReply:
        """
        Channel 层统一入口。

        各具体 Channel 适配器（web_chat / mcp / feishu / telegram 等）只需构造 ChannelMessage，
        再调用本方法即可获得统一格式的 ChannelReply。
        """
        # 渠道级配置：可用于默认角色 / 是否允许联网搜索等
        cfg = get_channel_config(message.channel)

        forced_role = None
        meta_forced_role = message.metadata.get("forced_role") if message.metadata else None
        if isinstance(meta_forced_role, str) and meta_forced_role.strip():
            forced_role = meta_forced_role.strip()

        # 若未显式开启 enable_web_search，则使用渠道默认策略
        if not enable_web_search and cfg.allow_web_search:
            enable_web_search = True

        # 从渠道元数据中提取通知目标，用于预警触发时主动下行消息
        notify_channel: Optional[Dict[str, Any]] = None
        if message.channel in ("telegram", "feishu"):
            chat_id_key = "tg_chat_id" if message.channel == "telegram" else "feishu_chat_id"
            chat_id = (message.metadata or {}).get(chat_id_key)
            if chat_id is not None:
                notify_channel = {"type": message.channel, "chat_id": chat_id}

        result = await cls.process_message(
            user_message=message.content,
            session_id=message.session_id,
            db=db,
            user=user,
            enable_web_search=enable_web_search,
            model=model,
            forced_role=forced_role,
            notify_channel=notify_channel,
            metadata=message.metadata,
        )

        return ChannelReply(
            channel=message.channel,
            session_id=message.session_id,
            user_id=message.user_id,
            content=result.get("content", ""),
            tool_outputs=result.get("tool_outputs"),
            metadata={},
        )
