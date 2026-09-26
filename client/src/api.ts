/** REST + SSE 封装：契约见 .trae/specs/implement-atoms-demo/spec.md「二、前后端交互契约」。 */

export interface ProjectSummary {
  id: number
  title: string
  owner_id: number | null
  share_id: string | null
  is_shared: boolean
  created_at: string
}

/** 登录用户（/api/auth/me）。 */
export interface AuthUser {
  id: number
  email: string
}

/** 认证（Task 13）：注册/登录成功即种 HttpOnly Cookie。 */
export function register(email: string, password: string): Promise<AuthUser> {
  return request('/api/auth/register', jsonInit('POST', { email, password }))
}

export function login(email: string, password: string): Promise<AuthUser> {
  return request('/api/auth/login', jsonInit('POST', { email, password }))
}

export function logout(): Promise<{ ok: boolean }> {
  return request('/api/auth/logout', { method: 'POST' })
}

export function getMe(): Promise<AuthUser> {
  return request('/api/auth/me')
}

export type StepKind = 'todo' | 'tool' | 'message'

export interface AgentStep {
  kind: StepKind
  agent: string
  content: string
  ts?: string
}

export type MessageRole = 'user' | 'agent'

export interface ChatMessage {
  id: number
  project_id: number
  role: MessageRole
  content: string
  steps: AgentStep[] | null
  created_at: string
}

/** 版本快照（Task 9）：列表不含 files 大字段。 */
export interface VersionInfo {
  id: number
  project_id: number
  label: string
  created_at: string
}

export interface ProjectDetail {
  project: ProjectSummary
  messages: ChatMessage[]
  files: Record<string, string>
  versions: VersionInfo[]
}

/** 回滚响应：恢复后的文件集 + 最新版本列表 + 落库的系统消息。 */
export interface RollbackResult {
  files: Record<string, string>
  versions: VersionInfo[]
  message: ChatMessage
}

/** GET /api/share/{shareId} 响应（访客侧，仅元信息）。 */
export interface ShareInfo {
  project_id: number
  title: string
  created_at: string
}

/** 422 校验错误的 detail 数组 → 取首条错误转中文（后端已转文案，这里兜底原始结构）。 */
function extractValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null
  const first = detail[0] as { msg?: unknown; loc?: unknown[] }
  let msg = typeof first?.msg === 'string' ? first.msg.replace(/^Value error,\s*/, '') : ''
  if (msg === 'Field required' || msg === 'Missing') msg = '不能为空'
  if (!msg) return null
  const field = first?.loc?.slice(-1)[0]
  const label = field === 'email' ? '邮箱' : field === 'password' ? '密码' : ''
  return label ? `${label}${msg}` : msg
}

async function errorMessage(res: Response): Promise<string> {
  const fallback = `请求失败（HTTP ${res.status}）`
  try {
    const data = (await res.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
    const validation = extractValidationDetail(data.detail)
    if (validation) return validation
  } catch {
    /* 响应体非 JSON 时使用兜底文案 */
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) throw new Error(await errorMessage(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  }
}

/** POST /api/projects {prompt} → 201 {id, title} */
export function createProject(prompt: string): Promise<{ id: number; title: string }> {
  return request('/api/projects', jsonInit('POST', { prompt }))
}

/** GET /api/projects → [{id, title, created_at}] */
export function listProjects(): Promise<ProjectSummary[]> {
  return request('/api/projects')
}

/** GET /api/projects/{id} → {project, messages, files} */
export function getProject(id: number): Promise<ProjectDetail> {
  return request(`/api/projects/${id}`)
}

/** DELETE /api/projects/{id} → 204 / 404 */
export function deleteProject(id: number): Promise<void> {
  return request(`/api/projects/${id}`, { method: 'DELETE' })
}

export interface ChatSSEHandlers {
  onStep?: (step: AgentStep) => void
  onFiles?: (files: Record<string, string>) => void
  onDone?: (summary: string) => void
  onStopped?: (message: string) => void
  onError?: (message: string) => void
  /** 排队位次（并发池）：position>0 排队中第 N 位；position=0 已轮到开始生成。 */
  onQueue?: (position: number, max: number) => void
  /** GET /events 专有：当前无活跃生成（旧后端兼容，新后端空闲时挂住长连接） */
  onIdle?: () => void
  /** GET /events 专有：项目有变更（另一设备发起生成/回滚/分享），提示拉取最新数据。 */
  onSync?: (reason: string, running: boolean) => void
}

/** POST /api/projects/{id}/stop → 协作式中断当前生成（已写文件保留） */
export function stopProject(id: number): Promise<{ stopping: boolean }> {
  return request(`/api/projects/${id}/stop`, { method: 'POST' })
}

/**
 * GET /api/projects/{id}/events：项目事件长连接（同账号多设备实时同步的数据通道）。
 * 有任务 → 重放已发生步骤并继续直播直到 done/stopped/error；空闲 → 服务端挂住，
 * 项目有变更时推 sync 事件。signal 可中断（收到 sync 后重连进直播等场景）。
 */
export async function eventsSSE(
  id: number,
  handlers: ChatSSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/projects/${id}/events`, { signal })
  if (!res.ok || !res.body) return // 404/网络异常：静默放弃重连

  const dispatch = (block: string): void => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      if (colon === -1) continue
      const field = line.slice(0, colon).trim()
      let value = line.slice(colon + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') dataLines.push(value)
    }
    if (dataLines.length === 0) return
    let payload: Record<string, unknown>
    try {
      payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
    } catch {
      return
    }
    if (event === 'step') {
      handlers.onStep?.(payload as unknown as AgentStep)
    } else if (event === 'files') {
      const files = payload.files
      handlers.onFiles?.(
        files && typeof files === 'object' ? (files as Record<string, string>) : {},
      )
    } else if (event === 'done') {
      handlers.onDone?.(typeof payload.summary === 'string' ? payload.summary : '')
    } else if (event === 'stopped') {
      handlers.onStopped?.(typeof payload.message === 'string' ? payload.message : '已停止')
    } else if (event === 'idle') {
      handlers.onIdle?.()
    } else if (event === 'sync') {
      // 项目变更通知（多设备同步）：reason = chat_start | gen_end | rollback | share
      handlers.onSync?.(
        typeof payload.reason === 'string' ? payload.reason : '',
        payload.running === true,
      )
    } else if (event === 'queue') {
      handlers.onQueue?.(
        typeof payload.position === 'number' ? payload.position : 0,
        typeof payload.max === 'number' ? payload.max : 0,
      )
    } else if (event === 'error') {
      handlers.onError?.(typeof payload.message === 'string' ? payload.message : '生成失败')
    }
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        dispatch(buffer.slice(0, sep))
        buffer = buffer.slice(sep + 2)
      }
    }
    const tail = decoder.decode()
    if (tail) buffer += tail
    if (buffer.trim()) dispatch(buffer.replace(/\r\n/g, '\n'))
  } finally {
    reader.releaseLock()
  }
}

/** POST /api/projects/{id}/versions/{vid}/rollback → 恢复文件集并生成新版本 */
export function rollbackVersion(id: number, versionId: number): Promise<RollbackResult> {
  return request(`/api/projects/${id}/versions/${versionId}/rollback`, { method: 'POST' })
}

/** POST /api/projects/{id}/share {enabled} → {share_id, is_shared} */
export function setShare(
  id: number,
  enabled: boolean,
): Promise<{ share_id: string | null; is_shared: boolean }> {
  return request(`/api/projects/${id}/share`, jsonInit('POST', { enabled }))
}

/** GET /api/share/{shareId} → 访客侧项目元信息（404 = 链接无效或已关闭） */
export function getShare(shareId: string): Promise<ShareInfo> {
  return request(`/api/share/${shareId}`)
}

/** ZIP 导出地址（a[href] 直接下载） */
export function exportUrl(id: number): string {
  return `/api/projects/${id}/export`
}

/**
 * POST /api/projects/{id}/chat：fetch + ReadableStream 消费 SSE。
 * 跨 chunk 缓冲解析 `event:` / `data:` 字段，按空行切分事件块；
 * 兼容 \r\n 行尾与 sse-starlette 的 `: ping` 注释帧。
 * HTTP 层错误（404 等）经 onError 回调，网络异常向上抛出由调用方兜底。
 * signal 可中断本地消费（后端生成不受影响，切回项目经 /events 重连直播）。
 */
export async function chatSSE(
  id: number,
  message: string,
  handlers: ChatSSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/projects/${id}/chat`, { ...jsonInit('POST', { message }), signal })
  if (!res.ok || !res.body) {
    handlers.onError?.(await errorMessage(res))
    return
  }

  const dispatch = (block: string): void => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      if (colon === -1) continue
      const field = line.slice(0, colon).trim()
      let value = line.slice(colon + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') dataLines.push(value)
    }
    if (dataLines.length === 0) return
    let payload: Record<string, unknown>
    try {
      payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
    } catch {
      return
    }
    if (event === 'step') {
      handlers.onStep?.(payload as unknown as AgentStep)
    } else if (event === 'files') {
      const files = payload.files
      handlers.onFiles?.(
        files && typeof files === 'object' ? (files as Record<string, string>) : {},
      )
    } else if (event === 'done') {
      handlers.onDone?.(typeof payload.summary === 'string' ? payload.summary : '')
    } else if (event === 'stopped') {
      handlers.onStopped?.(typeof payload.message === 'string' ? payload.message : '已停止')
    } else if (event === 'queue') {
      // 并发池排队位次（chat 流内也会推送）：position=0 表示已获得槽位开始生成
      handlers.onQueue?.(
        typeof payload.position === 'number' ? payload.position : 0,
        typeof payload.max === 'number' ? payload.max : 0,
      )
    } else if (event === 'error') {
      handlers.onError?.(typeof payload.message === 'string' ? payload.message : '生成失败')
    }
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        dispatch(buffer.slice(0, sep))
        buffer = buffer.slice(sep + 2)
      }
    }
    const tail = decoder.decode()
    if (tail) buffer += tail
    if (buffer.trim()) dispatch(buffer.replace(/\r\n/g, '\n'))
  } finally {
    reader.releaseLock()
  }
}
