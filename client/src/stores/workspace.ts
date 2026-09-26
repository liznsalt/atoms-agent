import { defineStore } from 'pinia'
import QRCode from 'qrcode'
import { reactive, ref } from 'vue'
import {
  chatSSE,
  eventsSSE,
  getProject,
  rollbackVersion,
  setShare,
  stopProject,
  type AgentStep,
  type ChatMessage,
  type ProjectSummary,
  type VersionInfo,
} from '../api'

/** 运行态消息：服务端 ChatMessage 加 pending 标记，SSE 收尾后落为普通消息。 */
export interface RunMessage extends ChatMessage {
  pending?: boolean
}

/** 历史错误消息的统一前缀（与后端落库文案一致）。 */
export const ERROR_PREFIX = '⚠️ 生成失败'

/** Stop 后后端落库的系统消息文案前缀。 */
export const STOPPED_PREFIX = '⏹ 已停止'

let localSeq = 0
let toastTimer: ReturnType<typeof setTimeout> | undefined

/**
 * 工作台状态（R1-R8）：messages / files / versions / generating / 队列，
 * loadProject 恢复项目，sendPrompt 乐观追加用户消息并流式接收；
 * 生成中新消息入队（可删），本轮结束（done/error/stopped）自动发下一条。
 */
export const useWorkspaceStore = defineStore('workspace', () => {
  /** 首页带入的待生成需求：R1 创建项目后自动开始首次生成。 */
  const pendingPrompt = ref('')
  const projectId = ref<number | null>(null)
  const project = ref<ProjectSummary | null>(null)
  const messages = ref<RunMessage[]>([])
  const files = ref<Record<string, string>>({})
  /** 版本快照列表（最新在前）。 */
  const versions = ref<VersionInfo[]>([])
  const generating = ref(false)
  /** Stop 已请求（后端取消标志已置位），等待 stopped 事件收尾。 */
  const stopping = ref(false)
  /** 消息队列（Task 14）：生成中的 follow-up 排队，可删除，本轮结束自动依序发送。 */
  const queue = ref<string[]>([])
  /** 预览运行时错误（Issue 自修复）：来自 iframe 的 window.onerror 上报。 */
  const issues = ref<{ message: string; source: string }[]>([])
  /** 并发池排队位次：0 = 未排队（空闲或已开始生成）；>0 = 排队中第 N 位。 */
  const queuePosition = ref(0)
  const queueMax = ref(0)
  const loading = ref(false)
  const loadError = ref('')
  /** 轻量操作提示（分享/回滚等），3 秒自动消失。 */
  const toast = ref('')
  /** 自增 nonce：变化即触发 iframe 重载（/preview/{id}?v=nonce）。 */
  const previewKey = ref(0)

  function bumpPreview(): void {
    previewKey.value += 1
  }

  function notify(text: string): void {
    toast.value = text
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toast.value = ''
    }, 3200)
  }

  function localMessage(
    role: 'user' | 'agent',
    content: string,
    steps: AgentStep[] | null,
    pending: boolean,
  ): RunMessage {
    localSeq -= 1
    return {
      id: localSeq,
      project_id: projectId.value ?? 0,
      role,
      content,
      steps,
      created_at: new Date().toISOString(),
      pending,
    }
  }

  /** 拉取项目详情（R5：刷新或从列表重开完整恢复）。 */
  async function loadProject(id: number): Promise<void> {
    closeWatch() // 断开旧项目的长连接与本地 chat 消费
    loading.value = true
    loadError.value = ''
    projectId.value = id
    project.value = null
    messages.value = []
    files.value = {}
    versions.value = []
    queue.value = []
    issues.value = []
    // 运行态随项目重置（项目级状态，互不残留：切项目前旧项目的
    // generating/stopping/queuePosition 不带进新项目）
    generating.value = false
    stopping.value = false
    queuePosition.value = 0
    try {
      const detail = await getProject(id)
      project.value = detail.project
      messages.value = detail.messages
      files.value = detail.files
      versions.value = detail.versions
      bumpPreview()
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : String(err)
    } finally {
      loading.value = false
    }
    // 后台可能有仍在跑的生成（离开页面不中断）→ 建立项目事件长连接（直播 + 空闲监听）
    if (!loadError.value) void watchProject(id, ++watchSeq)
  }

  /** 项目事件长连接世代号：loadProject/关闭时递增，旧 watch 循环据此退出。 */
  let watchSeq = 0
  let activeWatch: AbortController | null = null
  /** 当前项目 chat 流的本地消费控制（切项目时中断；后端生成继续，切回可经 /events 重连直播）。 */
  let activeChat: AbortController | null = null

  /** 离开项目页/切换项目：断开长连接、中断本地 chat 消费并让 watch 循环退出。 */
  function closeWatch(): void {
    watchSeq += 1
    activeWatch?.abort()
    activeWatch = null
    activeChat?.abort()
    activeChat = null
  }

  /** 空闲侧收到 sync(running=false)：全量拉取合并（回滚/分享/他端生成结束）。
   *  直播中不覆盖（本端 run 卡为 pending 本地态，全量覆盖会吃掉它）。 */
  function pullDetail(pid: number, seq: number): void {
    if (generating.value) return
    getProject(pid)
      .then((detail) => {
        if (projectId.value !== pid || watchSeq !== seq) return
        project.value = detail.project
        messages.value = detail.messages
        files.value = detail.files
        versions.value = detail.versions
        bumpPreview()
      })
      .catch(() => {
        /* 拉取失败：保持现状，下一次 sync 再合并 */
      })
  }

  /** 他端发起生成（sync chat_start）：先合并消息列表（拿到那条用户消息），不停预览。 */
  function pullMessages(pid: number, seq: number): void {
    getProject(pid)
      .then((detail) => {
        if (projectId.value !== pid || watchSeq !== seq) return
        messages.value = detail.messages
        versions.value = detail.versions
      })
      .catch(() => {})
  }

  /**
   * 项目事件长连接（同账号多设备实时同步）：
   * 有活跃生成 → 重放快照 + 直播；空闲 → 服务端挂住等 sync 通知。
   * sync(chat_start) → 拉消息后断开重连进直播；sync(其他) → 拉详情合并。
   * 连接意外断开 → 退避重连继续 watch，直到切换项目/离开页面（closeWatch）。
   */
  async function watchProject(pid: number, seq: number): Promise<void> {
    const alive = (): boolean => projectId.value === pid && watchSeq === seq
    let run: RunMessage | null = null

    const ensureRun = (): RunMessage => {
      if (!run) {
        generating.value = true
        stopping.value = false
        run = reactive(localMessage('agent', '', [], true))
        messages.value.push(run)
      }
      return run
    }
    const finish = (content: string): void => {
      const card = ensureRun()
      card.content = content
      card.pending = false
      run = null
      generating.value = false
      stopping.value = false
      queuePosition.value = 0
      bumpPreview()
      refreshVersions()
      // 注意：观看端不续跑消息队列——队列属于发起端（chat 流所在页面），
      // 多端各自续跑会双发；发起端收尾在 sendPrompt 的 finish 中处理。
    }

    for (let attempt = 0; alive(); ) {
      let resubscribe = false
      const controller = new AbortController()
      activeWatch = controller
      // 服务端每次订阅都全量重放快照：重连前清空已积累步骤，避免重复
      const existing = run as RunMessage | null
      if (existing) existing.steps = []
      try {
        await eventsSSE(
          pid,
          {
            onQueue: (position, max) => {
              queueMax.value = max
              queuePosition.value = position
              if (position > 0) {
                // 排队中：视为生成占用状态（可 Stop 取消排队）
                generating.value = true
                stopping.value = false
              }
            },
            onStep: (step) => {
              queuePosition.value = 0
              ensureRun().steps?.push(step)
            },
            onFiles: (next) => {
              ensureRun()
              files.value = { ...next }
              issues.value = [] // 预览内容更新后旧 Issue 过时
              bumpPreview()
            },
            onDone: (summary) => finish(summary),
            onStopped: (message) => finish(message),
            onError: (message) => finish(`${ERROR_PREFIX}：${message}`),
            onIdle: () => {
              /* 新后端空闲时挂住不推 idle；保留分支兼容 */
            },
            onSync: (reason, running) => {
              if (running) {
                // 发起端豁免：本端 chat 流就是数据源，watch 若也重连进直播
                // 会渲染出第二张 run 卡并重复推送步骤（多端同步后必须隔离）
                if (activeChat) return
                pullMessages(pid, seq)
                resubscribe = true
                controller.abort() // 断开重连 → 服务端已有活跃 ctx，重连即进直播
              } else if (reason !== 'chat_start') {
                pullDetail(pid, seq)
              }
            },
          },
          controller.signal,
        )
      } catch {
        /* abort 或网络断开：统一走下方重连判定 */
      }
      if (!alive()) break
      if (resubscribe) {
        attempt = 0
        continue // 立即重连进入直播
      }
      // 空闲/直播连接断开 → 退避重连（1.5s 起步封顶 10s）
      await new Promise((resolve) => setTimeout(resolve, Math.min(1500 * ++attempt, 10000)))
    }
  }

  /** 刷新版本时间线（生成成功/回滚后服务端已更新快照）。 */
  function refreshVersions(): void {
    if (projectId.value === null) return
    getProject(projectId.value)
      .then((detail) => {
        versions.value = detail.versions
      })
      .catch(() => {})
  }

  /**
   * 发送或入队（Task 14）：生成中 → 入队；空闲 → 直接发送。
   * 本轮结束（done/error/stopped/连接中断）后自动取队首继续。
   */
  function submit(text: string): void {
    const content = text.trim()
    if (!content) return
    if (generating.value) {
      queue.value.push(content)
      return
    }
    void sendPrompt(content)
  }

  /** 生成中移除排队消息。 */
  function removeQueued(index: number): void {
    queue.value.splice(index, 1)
  }

  /** Issue 自修复：预览运行时错误入列（同错误去重，最多 3 条防轰炸）。 */
  function pushIssue(message: string, source: string): void {
    if (issues.value.some((issue) => issue.message === message)) return
    if (issues.value.length >= 3) return
    issues.value.push({ message, source })
  }

  /** 一键自动修复：把错误描述发给 Engineer 走正常生成链路，随后清掉该 Issue。 */
  function resolveIssue(index: number): void {
    const issue = issues.value[index]
    if (!issue) return
    issues.value.splice(index, 1)
    submit(`应用预览出现运行错误，请修复：${issue.message}（位置：${issue.source}）。请定位并修正相关文件，保持其他功能不变。`)
  }

  function dismissIssue(index: number): void {
    issues.value.splice(index, 1)
  }

  async function sendPrompt(text: string): Promise<void> {
    const content = text.trim()
    if (!content || generating.value || projectId.value === null) return
    // 发起端角色：本条 chat 流绑定当前项目，切项目（closeWatch abort）后
    // 事件不再触碰全局状态（后端生成继续，切回经 watchProject 重连直播）
    const pid = projectId.value
    const controller = new AbortController()
    activeChat = controller
    generating.value = true
    stopping.value = false
    messages.value.push(localMessage('user', content, null, false))
    const run = reactive(localMessage('agent', '', [], true))
    messages.value.push(run)
    /** 本地消费被中断（切项目/离开页面）：静默退出，不动状态、不续跑队列。 */
    const aborted = (): boolean => projectId.value !== pid || controller.signal.aborted
    const finish = (summary: string): void => {
      run.content = summary
      run.pending = false
      if (aborted()) return
      queuePosition.value = 0
      bumpPreview() // DB 已提交（成功或 Stop 保留进度），刷新预览拿最终文件集
      refreshVersions()
      generating.value = false
      stopping.value = false
      // 队列自动依序执行下一条（仅发起端执行，多端不双发）
      const next = queue.value.shift()
      if (next) void sendPrompt(next)
    }
    try {
      await chatSSE(
        pid,
        content,
        {
          onQueue: (position, max) => {
            if (aborted()) return
            // 并发池排队位次（chat 流内）：position=0 已获槽位开始生成
            queueMax.value = max
            queuePosition.value = position
          },
          onStep: (step) => {
            run.steps?.push(step)
            if (!aborted()) queuePosition.value = 0
          },
          onFiles: (next) => {
            if (aborted()) return
            files.value = { ...next } // 全量文件集
            issues.value = [] // 预览内容已更新：旧 Issue 对应旧代码，若新内容仍报错会重新捕获
            bumpPreview()
          },
          onDone: (summary) => finish(summary),
          onStopped: (message) => finish(message),
          onError: (message) => {
            run.content = `${ERROR_PREFIX}：${message}`
            run.pending = false
            if (aborted()) return
            generating.value = false
            stopping.value = false
            queuePosition.value = 0
            const next = queue.value.shift()
            if (next) void sendPrompt(next)
          },
        },
        controller.signal,
      )
      if (run.pending) {
        // 流结束但既无 done/stopped 也无 error：按中断处理（R6 兜底）
        run.content = `${ERROR_PREFIX}：连接中断`
        run.pending = false
        if (aborted()) return
        generating.value = false
        stopping.value = false
        queuePosition.value = 0
        const next = queue.value.shift()
        if (next) void sendPrompt(next)
      }
    } catch (err) {
      // 主动中断（切项目/离开页面）：非错误，静默退出（后端生成继续）
      if (controller.signal.aborted || projectId.value !== pid) return
      run.content = `${ERROR_PREFIX}：${err instanceof Error ? err.message : String(err)}`
      run.pending = false
      generating.value = false
      stopping.value = false
      queuePosition.value = 0
      const next = queue.value.shift()
      if (next) void sendPrompt(next)
    } finally {
      if (activeChat === controller) activeChat = null
    }
  }

  /** Task 14 Stop：协作式中断，后端保留已写文件并推 stopped 事件收尾。
   *  stopping 超时兜底：stopped 事件异常未达（连接抖动等）时 10s 后自动复位，
   *  避免「停止中…」永久卡死（后续事件到达时 finish 会正常收尾）。 */
  async function stop(): Promise<void> {
    const pid = projectId.value
    if (pid === null || !generating.value || stopping.value) return
    stopping.value = true
    setTimeout(() => {
      if (projectId.value === pid && stopping.value && generating.value) {
        stopping.value = false
        notify('停止请求已发出，生成将在片刻后中断')
      }
    }, 10000)
    try {
      await stopProject(pid)
    } catch (err) {
      if (projectId.value !== pid) return
      stopping.value = false
      notify(`停止失败：${err instanceof Error ? err.message : String(err)}`)
    }
  }

  /** Task 9：回滚到指定版本（文件+预览恢复，回滚动作本身再落一条新版本）。 */
  async function rollbackTo(versionId: number): Promise<void> {
    if (projectId.value === null || generating.value) return
    try {
      const data = await rollbackVersion(projectId.value, versionId)
      files.value = data.files
      versions.value = data.versions
      messages.value.push(data.message)
      bumpPreview()
      notify(`已回滚至版本 v${versionId}`)
    } catch (err) {
      notify(`回滚失败：${err instanceof Error ? err.message : String(err)}`)
    }
  }

  /** 分享弹层（链接 + 二维码）：开启分享后展示，扫码/点链接均可查看项目。 */
  const showShare = ref(false)
  const shareUrl = ref('')
  const shareQr = ref('')

  function closeShare(): void {
    showShare.value = false
  }

  /** Task 11：一键分享开关；开启后弹二维码 + 链接，关闭后原链接即刻失效。 */
  async function toggleShare(): Promise<void> {
    if (projectId.value === null || !project.value) return
    const enabled = !project.value.is_shared
    try {
      const data = await setShare(projectId.value, enabled)
      project.value.share_id = data.share_id
      project.value.is_shared = data.is_shared
      if (enabled && data.share_id) {
        const url = `${location.origin}/share/${data.share_id}`
        shareUrl.value = url
        try {
          shareQr.value = await QRCode.toDataURL(url, { width: 260, margin: 1 })
        } catch {
          shareQr.value = '' // 二维码生成失败：降级为仅链接展示
        }
        showShare.value = true
        await navigator.clipboard.writeText(url).catch(() => {})
      } else {
        notify('分享已关闭，原链接即刻失效')
      }
    } catch (err) {
      notify(`分享设置失败：${err instanceof Error ? err.message : String(err)}`)
    }
  }

  return {
    pendingPrompt,
    projectId,
    project,
    messages,
    files,
    versions,
    generating,
    stopping,
    queue,
    issues,
    queuePosition,
    queueMax,
    loading,
    loadError,
    toast,
    previewKey,
    bumpPreview,
    notify,
    loadProject,
    closeWatch,
    submit,
    removeQueued,
    pushIssue,
    resolveIssue,
    dismissIssue,
    sendPrompt,
    stop,
    rollbackTo,
    toggleShare,
    showShare,
    shareUrl,
    shareQr,
    closeShare,
  }
})

