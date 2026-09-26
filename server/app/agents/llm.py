"""LLM 构造：支持 OpenAI 兼容与 Anthropic 兼容两种协议（LLM_PROVIDER 切换）。

- openai:     ChatOpenAI + LLM_BASE_URL（如 https://open.bigmodel.cn/api/paas/v4）
- anthropic:  ChatAnthropic + LLM_BASE_URL（如 https://open.bigmodel.cn/api/anthropic，
              GLM Coding Plan 订阅权益走此端点）
两者均为 LangChain BaseChatModel，deepagents 原样接受，工具调用行为一致。

前缀缓存（KV/Prefix Cache 的客户端侧控制）：
- anthropic 端点给请求尾块打缓存断点（system prompt + 工具定义 + 已累积对话整体
  进入服务端前缀缓存）；deepagents 工具循环的每一步都会重传全量对话历史，命中
  缓存可大幅降低 input token 与首 token 延迟。注意不能直接 ``bind(cache_control)``：
  deepagents 的 resolve_model 只认 BaseChatModel，bind 产物会被误当
  "provider:model" 字符串解析而报 partition 错，故子类化后在 bind_tools 产物上
  链式附加（kwargs 随调用透传到请求层，机制与官方 bind 用法一致）。
- openai 兼容端点的 prefix cache 由服务端自动命中（前缀一致即可），无需请求参数。
"""

from __future__ import annotations

from typing import Any

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROMPT_CACHE, LLM_PROVIDER


def get_chat_model() -> Any:
    """按 LLM_PROVIDER 构造流式聊天模型。

    高可用：统一 120s 请求超时 + 2 次自动重试（瞬时网络/限流抖动自愈，
    长任务不会无限挂死，重试耗尽后异常走 R6 错误卡片路径）。

    Returns:
        配置好的 BaseChatModel 实例（streaming；anthropic 默认附加前缀缓存标记）。

    Raises:
        RuntimeError: 未配置 LLM_API_KEY。
        ValueError: LLM_PROVIDER 非法。
    """
    if not LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY")
    kwargs: dict[str, Any] = {
        "api_key": LLM_API_KEY,
        "streaming": True,
        "timeout": 120,
        "max_retries": 2,
    }
    if LLM_BASE_URL:
        kwargs["base_url"] = LLM_BASE_URL
    if LLM_MODEL:
        kwargs["model"] = LLM_MODEL
    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not LLM_PROMPT_CACHE:
            return ChatAnthropic(**kwargs)

        class _PromptCachedAnthropic(ChatAnthropic):
            """带前缀缓存断点的 ChatAnthropic。

            deepagents 的 resolve_model 只接受 BaseChatModel（其余对象会被
            当作 "provider:model" 字符串 spec 解析，bind 产物即在此崩溃），
            所以不能返回 bind() 出来的 _ChatModelBinding。改为子类覆写
            bind_tools：LangGraph 内部对 BaseChatModel 调 bind_tools 绑定工具，
            在其产物上链式 bind cache_control——kwargs 随每次调用透传到请求
            组装层，展开为请求尾块的缓存断点（system + tools + 对话历史）。
            """

            def bind_tools(self, tools: Any, **tool_kwargs: Any) -> Any:
                return super().bind_tools(tools, **tool_kwargs).bind(
                    cache_control={"type": "ephemeral"}
                )

        return _PromptCachedAnthropic(**kwargs)
    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(**kwargs)
    raise ValueError(f"未知 LLM_PROVIDER: {LLM_PROVIDER!r}（应为 openai 或 anthropic）")
