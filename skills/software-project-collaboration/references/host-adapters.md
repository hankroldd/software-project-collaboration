# 跨宿主适配

核验日期：2026-11-04。先确认当前宿主和版本，再选对应入口；不要由模型名称推断宿主能力。

## 保持一份核心

使用标准目录式 Agent Skills：SKILL.md 的 name 与目录名一致，description 写清任务和触发条件；references、assets、scripts 使用相对路径，按需读取。
公共核心只保留可移植说明，不自动生成工具授权、hooks、subagent、team 或 MCP 配置。agents/openai.yaml 是宿主扩展，不能当作通用权限边界。
脚本使用 Python 3.10+ 标准库；联网安装器所需 Node 版本另见 [分发与维护](distribution.md)。
依据：[Agent Skills 规范](https://agentskills.io/specification)。

## 本地入口与发现

| 宿主 | 原生/兼容项目目录 | 常用个人目录 | 本套显式使用方式 |
| --- | --- | --- | --- |
| Codex CLI / IDE | .agents/skills；沿工作目录向仓库根发现 | ~/.agents/skills | $software-project-collaboration 或 /skills 列表 |
| Claude Code 本地终端 | .claude/skills；支持项目与嵌套目录 | ~/.claude/skills | /software-project-collaboration |
| OpenCode V1 | .opencode/skills；兼容 .claude/skills、.agents/skills | ~/.config/opencode/skills；兼容 ~/.claude/skills、~/.agents/skills | 请其加载该技能；模型工具使用 name 字段 |
| OpenCode V2 | 同时读取 .opencode/skills、.claude/skills、.agents/skills | 同上；还支持显式配置来源 | @software-project-collaboration；模型工具使用 id 字段 |

目录中的入口均为 software-project-collaboration/SKILL.md。表中的个人路径是默认值；宿主可有配置目录覆盖，使用前核实际环境。
不要把 Claude 的 /skill-name 套到 OpenCode，也不要把 ChatGPT 的 @技能界面推断为 CLI 语法。
CLI 安装器的目标目录与宿主支持的全部目录不同：skills@1.7.6 将 Codex、OpenCode 共用内容写到 .agents/skills，给 Claude 建立 .claude/skills 入口；全局安装同样以 ~/.agents/skills 为共同目录。

Codex 的当前文档将 .agents/skills 作为本地入口，并建议通过插件共享更完整的可复用能力包；插件分发与目录式技能可以并存，不能声称普通目录安装等于账户或云端安装。
Claude 的个人目录不随本机文件自动进入 Cowork 或云会话；账户同步技能另有机制，不向 synced 目录写自定义文件。

来源：[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)、[OpenCode V1](https://opencode.ai/docs/skills)、[OpenCode V2](https://opencode.ai/v2/docs/skills)。

## 同名技能与共享目录

| 场景 | 已核实规则 | 工作要求 |
| --- | --- | --- |
| Codex 多处同名 | 不合并；列表中可能出现多个同名技能 | 检查实际来源，不假设项目覆盖个人 |
| Claude 同名目录 | 企业高于个人，个人高于项目；插件有命名空间 | 不在个人和项目安装不同版本后依赖项目覆盖；排查时检查个人来源 |
| Claude 同一真实目录的符号链接 | 多处指向同一目标时只加载一次 | 核链接目标；不要复制出不同内容冒充单一来源 |
| OpenCode V2 同 ID | 后注册覆盖；兼容 .claude 早于 .agents，原生 OpenCode/显式来源可更晚 | 清点所有来源；不要借重复 ID 暗中覆盖 |
| CLI 共用 .agents 目录 | Codex 和 OpenCode 读取同一份物理内容 | --agent 是安装目标选择，不是“仅此宿主可读”的隔离控制 |

共享同一来源时选一种安装渠道和一种主要作用域。不要将同一套内容同时用全局 CLI、项目副本、账户同步与插件重复安装。
需要宿主专有配置时另建适配层，记录责任人和适用版本；更新核心不自动改其权限。
CLI 的同名覆盖、锁文件、更新和卸载细节见 [分发与维护](distribution.md)。

## OpenCode V1 与 V2 分开处理

V1 的技能加载工具形态是 skill({name: "software-project-collaboration"})，权限属于 permission.skill 的模式映射。
V2 由路径确定 ID，frontmatter 的 name 只作显示名；加载形态是 skill({id: "software-project-collaboration"})，用户可写 @software-project-collaboration。
V2 权限使用 permissions 规则数组，action 为 skill、resource 为技能 ID；匹配顺序有意义，后匹配规则优先。
两版都可加载本套标准目录；保留 name、description 与目录名一致，避免依赖 V2 放宽的格式。
不要把 V1 的 permission 对象复制成 V2 配置，也不要为“一键安装”添加允许全部工具的设置。
官方同时提供 [V1](https://opencode.ai/docs/skills) 与 [V2](https://opencode.ai/v2/docs/skills) 文档；以实际版本匹配，不把搜索到的新页面当已运行的客户端证据。

## 项目规则与跨 harness 接续

AGENTS.md 记录短的共同规则、关键命令和文档入口；需要 CLAUDE.md 时使其引导读取共同规则，避免复制出第二套事实。
业务任务按实现、审查、验收和集成分工，不因 GPT/Claude 等模型标签自动分配“擅长岗位”。
跨会话、模型或 harness 接续时，按模块 11 交付任务 ID、BASE/HEAD、工作树、已有改动、证据、未闭合问题和下一步。
对每位执行者核实际 cwd、可写目录、分支和工具边界；宿主宣称支持 worktree、subagent 或 teams 不等于本次调用已经隔离。
Claude 的某种子代理调用可能成为 teammate，定义中的技能和隔离选项不能一概视作团队运行时保证；实际角色加载与工作目录必须核对。
无法使用某条宿主命令时，读取已知真实文件执行对应步骤并报告差异；不假装命令、插件或钩子已经运行。
依据：[Claude sub-agents](https://code.claude.com/docs/en/sub-agents)、[Claude agent teams](https://code.claude.com/docs/en/agent-teams)。

## 与社区技能共存

一次任务明确一个流程主持者；本套负责路由时，社区技能补充局部能力。项目已由 OpenSpec、Spec Kit、BMAD、Superpowers 或其他流程组织时，沿用其有效状态和门禁。
安装多个技能不等于必须同时启动多个全局编排器。发生冲突时写明当前主持者、采用的步骤和不适用的部分。
不要机械叠加“每一步确认”“所有修改都固定 TDD”“必须发现若干问题”等机制；以用户已有授权、当前项目要求和实际风险确定流程。
第三方安装固定来源、版本和范围；普通开发不自动联网升级工作协议。严格门禁确实适用时，不借“精简”绕过它。

## 验证与如实报告

分开记录三种证据：

1. **格式和文件证据**：入口、相对路径、脚本 --help、源版本以及复制/链接后内容一致。
2. **安装器证据**：在隔离项目安装、列出、更新或卸载后的目录与锁文件；说明实际命令和版本。
3. **宿主运行证据**：在指定版本客户端发现技能、显式调用、正确路由一项任务，且未无故加载无关模块。

前两项通过不代表第三项通过。Windows 的链接回退、不同版本客户端、云端或账户同步若未运行，分别列为未验。
只验证与本次变更相关的能力；不要为了凑“全平台”重复执行不必要的真实开发或部署操作。
