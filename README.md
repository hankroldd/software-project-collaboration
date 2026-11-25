# Software Project Collaboration

一套面向真实软件项目的协作技能：把需求、设计、实现、验证、发布和运维连在一起，并让人工、多个 agent 与不同开发宿主能够接续工作。

**一个入口，按需读取十二个工作模块。** 小改动走轻流程，跨接口、权限、迁移和发布等任务保留相应契约与证据。已有 OpenSpec、Spec Kit、Superpowers 或项目流程时沿用原主持者和文档，不另建第二份总账。

本仓库提供 Agent Skills 格式的 Markdown、模板与可选 Python 标准库工具。Claude Code、Codex、OpenCode 可通过各自技能发现机制读取；权限、hooks、子代理和会话仍由宿主管理。

## 快速安装

前提：Node >=22.20.0、npm、可用 Git，以及对本仓库及所选版本的访问权限。在真正的目标项目根目录执行：

```bash
npx --yes skills@1.7.6 add "hankroldd/software-project-collaboration#v0.3.0" --skill software-project-collaboration --agent claude-code --agent codex --agent opencode --yes
```

这是一条首次项目安装命令。仓库和 ref 必须已经发布才可联网安装。安装器版本和技能源版本分别固定；需要不可变来源时，将 tag 换成已核对的完整提交 SHA。

**已有同名技能先检查。** `--yes` 接受同名覆盖，安装器会重建目标，不自动合并本地修改。默认 Codex 与 OpenCode 共用 `.agents/skills`，Claude 使用 `.claude/skills` 入口；`--copy` 使用独立副本，更新后需核对内容一致性。只需要部分宿主时移除相应 `--agent`，但这不阻止另一兼容宿主读取共享目录。

默认项目安装；个人跨项目安装才显式加 `--global`。把项目 `skills-lock.json` 提交到项目仓库。CLI 默认遥测及远程审计请求可通过 `DISABLE_TELEMETRY=1` 或 `DO_NOT_TRACK=1` 关闭，获取包与技能源仍需要网络。详细来源、更新、回退、卸载、Windows 与离线方式见[分发说明](skills/software-project-collaboration/references/distribution.md)。

## 开始使用

向当前开发宿主明确提出：“使用 software-project-collaboration，结合这个仓库和已有约定完成……”。Codex 通常可用 `$software-project-collaboration`，Claude Code 可用 `/software-project-collaboration`；OpenCode 的标识与调用按所用 v1/v2 版本确认，见[宿主适配](skills/software-project-collaboration/references/host-adapters.md)。

可以直接说：

- “接手这个已有项目，先看真实状态，再修复保存后回读丢失 false/0 的问题。”
- “为这个新项目初始化必要 docs，确认 spec、API 合同与第一个可运行纵向切片。”
- “两个人和两个 agent 分做前后端，明确工作树、共享数据库、契约与集成人。”
- “让 Codex、Claude Code 和 OpenCode 接续同一项目，整理消息确认、共享事实、状态更新与交接。”
- “审查当前候选；结论绑定 BASE/HEAD，允许零发现，保留上次未关闭问题。”
- “把这个功能部署到已授权环境，核运行版本、关键路径与回退条件。”

需要宿主重新发现技能时按该宿主文档重开会话或刷新。文件存在、安装器成功和真实任务运行通过是三个不同结论。

## 体系

| 工作 | 模块 |
| --- | --- |
| 优先级、范围、可观察验收 | [需求与规格](skills/software-project-collaboration/references/01-requirements-spec.md) |
| 项目脚手架、docs、指令入口、依赖 | [项目初始化](skills/software-project-collaboration/references/02-project-bootstrap.md) |
| API、数据、权限、状态、复用 | [架构与契约](skills/software-project-collaboration/references/03-architecture-contracts.md) |
| 前端、UI、交互、键盘、文案 | [前端与体验](skills/software-project-collaboration/references/04-frontend-ux.md) |
| 纵向实现与范围控制 | [开发实现](skills/software-project-collaboration/references/05-implementation.md) |
| 复现、假设、因果验证、回归 | [根因排障](skills/software-project-collaboration/references/06-debugging.md) |
| 分层测试、独立审查、证据 | [验证与审查](skills/software-project-collaboration/references/07-verification-review.md) |
| 构建、迁移、部署、回退 | [发布部署](skills/software-project-collaboration/references/08-release-deployment.md) |
| 监控、故障、恢复、成本 | [运维维护](skills/software-project-collaboration/references/09-operations.md) |
| Dify、模型、流式与事实质量 | [AI 集成与评测](skills/software-project-collaboration/references/10-ai-integration.md) |
| 多人、多 agent、多 harness | [协作与交接](skills/software-project-collaboration/references/11-parallel-handoff.md) |
| 文档职责、清楚表达、去 AI 味 | [文档与表达](skills/software-project-collaboration/references/12-docs-writing.md) |

需求优先级、工程风险和缺陷严重度分别定义；已有项目等级先映射。本套 R0—R3 是用于选择流程的设计，不宣称行业统一分级。

## 协作规则

共同任务明确目标、允许写入范围、BASE/HEAD、负责人、集成人和共享资源。同一工作树默认同一时间只有一个写入者；明确不交叠文件的并行例外仍需指定 Git、生成文件与公共记录的唯一维护者。独立工作树仍需分别安排端口、数据库、卷和外部副作用。

跨宿主传递任务合同、补丁/提交、证据和未关闭问题，不假设本地 team 锁、hooks 或权限自动互通。超时不能自动转移写入权；接管核实旧进程与结果，迟到结果先比对再采用。共同候选经过集成验证后，才能形成整体完成结论。

详见[协作协议](skills/software-project-collaboration/references/collaboration-protocol.md)、[工作流冲突处理](skills/software-project-collaboration/references/workflow-governance.md)和[模板索引](skills/software-project-collaboration/references/templates-and-tools.md)。

### 代理通信与共享项目信息

消息用于派发、提问、通知变更和交回结果；项目文档与任务记录保存经过核实的当前事实。沿用已有 Issue、PR、OpenSpec 变更目录或团队文档，不要求额外部署消息服务或知识库。

| 需要解决的问题 | 具体约定 |
| --- | --- |
| 消息发出了，对方是否采用 | 区分已发送、已收到、已接受、已集成；关键交接指向明确的接收方与结果记录 |
| 多个 agent 各有一份项目理解 | 为目标、契约、任务、决策、证据、运行版本指定各自主记录与维护者；共享索引只保存入口 |
| 旧消息与新契约冲突 | 对比任务/尝试、契约修订和候选身份；不按消息到达时间覆盖事实 |
| 所有人同时修改 STATUS | 工作者提交事实与更新建议，由记录维护者按当前修订合并；不同记录可有不同维护者 |
| 换模型、换会话或换宿主 | 交接最小上下文、未决消息、未接受结果和责任；接手后核对真实仓库与运行状态 |
| 长期维护导致文档过期 | 在契约变更、任务集成、发布和交接时更新相关记录；保留决策来源与取代关系，归档已关闭过程 |

详见[消息与项目共享信息](skills/software-project-collaboration/references/agent-communication-and-project-memory.md)，并按需使用消息、共享信息索引、任务卡、交接和集成模板。这些是可移植的协作约定；实际消息投递、权限、互斥和任务调度由所用工具承担。

## 可选工具

运行 Python 3.10+ 标准库脚本前先看 `--help`。它们不代替宿主权限或 CI：

| 工具 | 作用 |
| --- | --- |
| `bootstrap_project.py` | 预览并只创建必要 docs 与事实配置，不选栈或安装依赖 |
| `repo_snapshot.py` | 固定仓库身份与近期变更索引，不冒充审查 |
| `check_evidence.py` | 检查验收覆盖、状态、候选与文件哈希，不判断业务语义 |
| `export_skill.py` | 离线 create-only 快照，不接管联网更新与卸载 |
| `inspect_installation.py` | 只读比较指定项目的同名副本与链接 |
| `prepare_repository.py` | 为维护者生成可审查发布候选，不联网、提交或发布 |

## 验证与维护

```bash
python3 tools/validate_repository.py --check-manifest
python3 -m unittest discover -s skills/software-project-collaboration/scripts -p "test_*.py" -v
```

仓库 CI 定义 Linux 上 Python 3.10/3.13 的结构检查与合成工具测试。某次 CI 是否实际通过以该提交的运行记录为准；这些测试不启动三个宿主，也不验证真实部署或模型质量。技能行为评估用实际任务和原始夹具，预期结果由评估者单独保管。

更新公共内容后审查 diff、运行检查，再显式执行 `python3 tools/validate_repository.py --refresh-manifest` 更新内容清单。清单只证明文件集合与哈希自洽，不是签名、发布凭证或效果证明。发布步骤见[维护与发布](docs/RELEASING.md)。

## 来源与许可

当前内容版本：0.3.0。采用 Agent Skills 的渐进加载方式，参考 Ponytail、Superpowers、OpenSpec、Spec Kit、官方宿主与工程文档，并明确采纳范围。详见[来源与采用边界](skills/software-project-collaboration/references/sources.md)及[第三方说明](THIRD_PARTY_NOTICES.md)。

原创内容使用 [MIT](LICENSE)。技能子目录另含 `LICENSE.txt`，单技能安装时仍保留许可。贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)；不要提交私人仓库证据、聊天摘录、客户信息或凭据。
