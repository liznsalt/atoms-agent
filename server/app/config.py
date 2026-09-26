import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
# LLM 协议：openai（OpenAI 兼容 /v1）或 anthropic（Anthropic 兼容，如 GLM Coding Plan）
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
# Anthropic 端点前缀缓存（prompt caching）：cache_control 绑定到请求尾块，
# system+工具定义+已累积对话整体缓存，deepagents 工具循环每步重传全量历史时命中。
# 设为 0 可关闭（端点不兼容缓存标记时）。
LLM_PROMPT_CACHE = os.getenv("LLM_PROMPT_CACHE", "1") != "0"
# 上下文压缩：拼入 prompt 的文件集总字符上限，超出则截断非入口文件（头尾保留+省略标注）
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "60000"))
