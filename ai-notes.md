# AI 服务接口

`AIService(data_dir)` 提供设置、模型候选、任务提交、查询与自动整理。HTTP 提交：`POST /api/ai/jobs {mode, topicId, ideaIds?, includeDescendants?, model?, prompt?}`。省略 `ideaIds` 处理整个主题；显式空数组拒绝。所选 ID 必须有效、唯一且属于该主题。`GET /api/ai/models?provider=codex|api` 返回 `{models:[{id,name}], source, warning?}`；API 模型查询仅本机所有者可执行。

设置字段：`provider: codex | api`、`model`、`apiBase`、`customPrompt`、`autoMode: off | organize | develop`，以及仅写入的 `apiKey`。省略 `apiKey` 保留现有密钥；空字符串清除保存的密钥。GET 用 `hasApiKey` 表示密钥状态，不返回密钥。Windows 使用当前账户 DPAPI 加密；其他系统通过 `SPARKSPACE_AI_API_KEY` 环境变量提供密钥。本机无认证 API 可留空密钥。API 接口须兼容 `/chat/completions` 和 `response_format: {type: json_object}`。

单次 `model`、`prompt` 缺省时使用保存的默认配置；显式空提示词表示本次不附加默认要求。任务回传当次范围、模型和要求。上下文将选中记录标为 target，必要祖先标为 background；改写或移动建议只能指向 target，新分支也必须挂到目标范围内。统计明示目标、背景和省略数量；活动任务去重包含模型、提示词及所选范围。旧设置/任务保持兼容，不会重跑。

作业的 `baseRevision` 用于前端判断建议是否过期；`trigger` 是 `manual` 或 `auto`。`result` 始终是建议，不会修改工作区。采纳改写时应另存分支并保留原文。`contextStats` 明示上下文的省略与截断，最多传递 80 条主题/灵感记录、120000 字符。全部主题模式为每个纳入主题分配背景与约束额度；单主题模式只为其他主题提供分类摘要，其主动省略单独计入 `overviewOmissions`，不混入 `truncatedFields`。自动模式默认关闭，启用后在最后一次有效保存 25 秒后处理最近改动的主题，忽略倒序版本通知；忙时保留最新待分析版本。队列最多容纳两个活动作业，同一活动任务去重，不自动重试失败；重启将 queued/running 标记 failed。

Codex 模型留空时使用 CLI 默认模型值，调用通过 `--ignore-user-config` 绕开全局插件配置，仍使用本机登录。使用独立 `data/ai-work` 临时目录、read-only 沙箱、无 shell 的隐藏进程与 300 秒超时，并关闭命令、插件、应用、浏览器、多代理、记忆等工具入口。API 请求不跟随重定向，远程地址必须为 HTTPS；HTTP 仅支持 localhost 或回环 IP。stderr、stdout、密钥及 API 原始错误不会返回页面。

验证：`python test_ai.py` 覆盖设置与 DPAPI、JSON/ID 校验、上下文上限、API 请求/认证错误/重定向、队列去重、超时、防抖、重启和原工作区保留。`python test_ai.py --live` 会实际调用本机 Codex，输入仅为测试文件中的虚构港城；2026-09-11 实测 completed，81.7 秒、5 条合格建议，未指定模型。此测试确认 CLI 当前可用，不证明实际后端型号；没有使用真实外部 API key 做付费 API 验证。
