# 分发、安装与维护

核验日期：2026-11-04。此页用于将技能交付给团队、安装到本地 harness 或维护既有安装；普通开发不需要加载。

## 目录

- 安装渠道与版本
- 快速安装
- 目录、重名与覆盖
- 列出、检查、更新与卸载
- 离线导出与 Windows
- 隔离验证
- 公开发布边界
- 核验依据

## 安装渠道与版本

默认复用社区的 vercel-labs/skills CLI，固定 skills@1.7.6；不维护第二个联网包管理器。
该版本官方发布于 2026-11-03，对应提交 7a5e920bead4b1039a6d6df5d7e1163b7b09423a，声明 Node >=22.20.0。
联网安装需要 npm 包源和技能仓库可访问；Git 来源的克隆、认证或回退还需要可用 Git。先核来源、授权和目标目录，再执行安装。
技能本身的 Python 脚本与安装器依赖分开：阅读 Markdown 不需要 Node，运行本套脚本需要 Python 3.10+。

固定两个版本：安装器版本与技能来源 ref。新 CLI 可能改变行为；升级安装器后重新做相关兼容验证。
npx 固定顶层包版本不等于锁定其全部依赖；需要严格复现安装环境时，记录实际依赖并使用有锁文件的受控工具环境。
仓库中的发布说明可以给一条命令，但不能把 OWNER/REPO、TAG_OR_FULL_SHA 占位符写成已上线的来源。
本页命令中的 OWNER/REPO 必须替换为实际公开或已授权访问的仓库；TAG_OR_FULL_SHA 必须替换为已发布 tag 或完整 40 位提交 SHA。
OWNER/REPO@NAME 在该 CLI 中选择技能，不表示版本；固定 Git ref 使用 #。

## 快速安装

在目标项目根执行。下面是一条首次项目安装命令；--yes 同时接受已存在同名目标的覆盖，因此已有安装先按后文检查。

```bash
npx --yes skills@1.7.6 add "OWNER/REPO#TAG_OR_FULL_SHA" --skill software-project-collaboration --agent claude-code --agent codex --agent opencode --yes
```

准确 agent ID 是 claude-code、codex、opencode。不要改成 claude、open-code 或模型名称。
不需要三个宿主时删去对应 --agent；共享目录的可见性仍按宿主实际发现规则决定。
默认项目范围；需要个人跨项目可用时显式添加 --global，不在脚本里偷偷启用。
命令应在真正的目标根运行，不在个人主目录冒充项目执行。

先查看来源与已有安装时使用：

```bash
npx --yes skills@1.7.6 add "OWNER/REPO#TAG_OR_FULL_SHA" --list
npx --yes skills@1.7.6 list
npx --yes skills@1.7.6 list --global
```

使用可读的发布 tag 便于团队交流；需要精确复现时固定完整 SHA。tag 可被移动，不能当作密码学不可变身份。
已固定 SHA 的安装不会因仓库发布新 tag 自动切换版本。

CLI 默认有使用遥测；DISABLE_TELEMETRY=1 或 DO_NOT_TRACK=1 可关闭，同时会关闭 CLI 的远程安全审计请求。
POSIX shell 可在单条命令前加 DISABLE_TELEMETRY=1；PowerShell 使用该进程的 $env:DISABLE_TELEMETRY = "1"。
这不关闭获取 npm 包、GitHub 元数据或技能源所需的网络，也不替代人工核对第三方内容。

## 目录、重名与覆盖

| 范围/方式 | Codex 与 OpenCode | Claude Code | 锁文件 |
| --- | --- | --- | --- |
| 默认项目链接安装 | 项目 .agents/skills/software-project-collaboration | .claude/skills 下链接到共同目录 | 项目根 skills-lock.json |
| --global 链接安装 | ~/.agents/skills/software-project-collaboration | 默认 ~/.claude/skills 下链接到共同目录 | ~/.agents/.skill-lock.json；设置 XDG_STATE_HOME 时改用其 skills 子目录 |
| --copy | 仍共用 .agents 目标 | 独立复制到 .claude/skills | 记录 copy 模式，供更新沿用 |

表格说明的是 skills@1.7.6 的行为，不是各宿主所有可读目录。OpenCode 原生的 .opencode/skills 另有用途，CLI 不额外创建第三份核心。
Claude 全局路径可受 CLAUDE_CONFIG_DIR 影响。--agent 选择目标，不禁止其他兼容宿主读取 .agents。
默认“symlink 安装”会先复制内容到共同目录，再链接宿主入口；并非持续链接到原 Git 克隆，原克隆变化不会自动更新已安装内容。

CLI 以技能名称作为锁文件键，同名不同来源不能靠锁文件同时管理。
安装摘要标记 overwrites，实际安装清理并重建目标；--yes 跳过最终确认。
它没有为本地改动做三方合并或自动备份。团队定制在源仓库或明确的派生技能中维护，升级前保存需要保留的修改。
遇到已有不同来源、个人/项目双份或插件同名，先核实际来源和内容，再选择保留哪个；不要靠宿主优先级掩盖冲突。

把项目 skills-lock.json 纳入版本控制，核 source、ref、skillPath 与哈希。全局锁记录本机安装状态，不复制到业务仓库。
锁文件记录来源与内容身份，不能证明宿主已经加载，也不是并发修改锁；安装/更新/卸载由一位集成人顺序执行，避免多个 harness 同时改同一安装目录和锁文件。

## 列出、检查、更新与卸载

```bash
npx --yes skills@1.7.6 list --agent claude-code --agent codex --agent opencode
npx --yes skills@1.7.6 check software-project-collaboration --project
npx --yes skills@1.7.6 update software-project-collaboration --project --yes
npx --yes skills@1.7.6 remove software-project-collaboration --yes
```

check 只报告；发现可更新内容或检查失败时都可能返回 1，结合输出区分，不把所有非零退出码解释成安装损坏。
check/update 支持 --project 或 --global；更新时写明作用域和技能名，避免无参数批量更新所有工作协议。
remove 默认当前项目；移除个人安装时加 --global。remove 不提供与 update 等价的 --project 必需标志，使用正确 cwd 和默认项目范围即可。

更新保留安装记录中的 ref 与 copy 模式。跟踪分支时 update 可取分支新内容；固定 SHA 时它不会追踪“最新 release”。
需要从一个固定版本升级到另一个版本时，审查差异后重新执行 add，换成新 ref；回退同理使用原 ref。
check/update 的比较主要依据远端与锁文件；不能把“up to date”当本地文件未被编辑的证明。
本地编辑可能在远端未变时保留，在后续重新安装时被清理；需要保留的更改应回到受控源。

上述 remove 不按 --agent 缩小目标：它会对该名称检查所有已知宿主目录，清除相应入口与不再使用的共同目录。
它不移除其他名称的技能。执行前仍需确认该名称确属本套，防止删除独立同名定制。
指定 --agent 的部分卸载会尝试保留其他已检测宿主仍使用的共同目录及锁记录；这不等于隔离读取。
Codex 和 OpenCode 共用 .agents，不能通过删除其中一个安装目标让另一方保留同名文件、同时禁止前者读取；改用宿主自己的显式启用/权限规则并逐项验证。
不要使用 --all 批量卸载来解决单个技能问题。

## 离线导出与 Windows

离线环境使用已审核的完整技能目录或本套 export_skill.py。它仅做项目范围、显式、create-only 的快照导出，不承担远端发现、更新、卸载或宿主设置修改。
在技能目录执行：

```bash
python3 scripts/export_skill.py --root /ABSOLUTE/PROJECT --target all
python3 scripts/export_skill.py --root /ABSOLUTE/PROJECT --target all --apply
```

先预览，--apply 才写入；已相同的内容幂等，已有差异拒绝覆盖。
all 映射共享 .agents 与 Claude .claude 两个入口；opencode 与 codex 的目标相同，不额外创造 .opencode 副本。
导出不生成社区 CLI 的安装锁，不能声称 skills update/remove 已经接管这些快照。
后续升级应先比较现有内容与旧源，保存本地定制，再由维护者明确迁移；脚本拒绝冲突时不加隐藏的强制覆盖开关。
离线时脚本可处理已有文件，不会替用户下载 Node、npm 包、宿主、模型或技能。

CLI 在 Windows 使用目录 junction 创建链接，并可在失败时退回复制；也可显式 --copy。
复制模式需在更新后核内容是否一致，不把“安装完成”视为链接已成功。
若从 Git 克隆了含 POSIX 链接的项目，Windows 上的检出结果也需实际核对；必要时用 CLI 重新安装或明确复制模式。
一行 npx 命令可用于常见 shell；多行续行、环境变量及 Python 启动命令按操作系统调整。未运行的平台不要写成“全部兼容已实测”。

## 隔离验证

安装器烟测只在临时项目执行无 --global 的命令，并将 npm cache、XDG_STATE_HOME、XDG_CONFIG_HOME、CLAUDE_CONFIG_DIR 指向测试目录；保留 HOME 与 CODEX_HOME。
使用显式 --agent，源使用已审核的本地候选目录；验证 .agents 入口、.claude 入口、两处内容、项目锁，然后列出和移除指定名称。
在此临时项目移除该名称时不加 --agent，避免其他通用宿主检测影响共同目录清理；不使用 --all。
测试联网 Git ref、固定 SHA、更新与回退时另用受控测试源，记录 ref、命令、退出码和锁文件，不触碰用户真实全局安装。
实际宿主发现、显式调用和任务行为是另一级测试，按 [跨宿主适配](host-adapters.md) 分别报告。

## 公开发布边界

公开仓库外层容纳 README、版本说明、许可证、贡献规则和 CI；安装目录保持标准技能结构。私有项目证据、会话摘录、内部路径、账号配置、令牌和个人策略不进入公共发行内容。
对本套自写内容明确作者与所选许可证；采用的第三方代码逐项核许可证、保留必要声明。许可模板未填写时不能声称已具备确定开源授权。
先生成可审查候选和版本清单，再根据已有授权决定是否创建远端仓库、公开可见性或发布 release。“考虑发布”不自动等于授权公开。
同一版本维护一份核心；Claude/Codex 插件包装如有实际需求再增加，不自动安装 hooks、MCP 或 team 设置，也不同时启用与目录安装相同的技能。
Claude 的 .claude-plugin/plugin.json 若放入个人/项目技能目录可改变其加载方式，应将可选插件包装与通用技能根分开。
普通 GitHub 技能仓库不需要 npm 包、HTTP 技能目录或 experimental_sync 才能安装；避免为首次分发叠加多个分发系统。

需要首次生成完整候选时，在已审核的技能目录运行：

```bash
python3 scripts/prepare_repository.py --root /ABSOLUTE/NEW-REPO --repository OWNER/REPO --release-ref v0.3.0
python3 scripts/prepare_repository.py --root /ABSOLUTE/NEW-REPO --repository OWNER/REPO --release-ref v0.3.0 --apply
```

该维护工具使用 assets/publishing 模板并复制一份技能核心；保留 skill-local LICENSE.txt，OpenAI 元数据只带 interface。它只创建本地候选，不查远端、不执行 Git、不创建仓库或 release；发现不同既有文件时整个计划拒绝写入，也不自动清理额外文件。
生成后按候选 README 运行结构/清单检查和合成工具测试，审查完整发布树，再执行已授权的远端发布。发布后以真实来源SHA补安装、锁与所需宿主加载验证。此生成器不替代公共仓库后续直接维护或社区安装器。

## 核验依据

以下代码链接固定在 skills v1.7.6 发布提交，升级版本后重新核查行为。

- [发布记录](https://github.com/vercel-labs/skills/releases/tag/v1.7.6)
- [Node 要求](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/package.json)
- [命令说明](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/docs/commands.md)
- [agent 映射](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/agents.ts)
- [安装、链接与覆盖](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/installer.ts)
- [来源 ref 解析](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/source-parser.ts)
- [项目锁](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/local-lock.ts)与[个人锁](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/skill-lock.ts)
- [更新](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/update.ts)与[ref 保留](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/update-source.ts)
- [卸载](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/remove.ts)
- [遥测和审计开关](https://github.com/vercel-labs/skills/blob/7a5e920bead4b1039a6d6df5d7e1163b7b09423a/src/telemetry.ts)
- [Claude 插件与独立技能](https://code.claude.com/docs/en/plugins)、[技能目录中的插件](https://code.claude.com/docs/en/skills)
