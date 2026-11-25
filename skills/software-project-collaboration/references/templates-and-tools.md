# 模板与工具

## 使用原则

模板只用于任务需要的产物。R0 通常一段完成说明即可；R1 可用短任务卡；R2/R3 再采用变更 spec 和证据。
若仓库已有对应结构，填其字段并引用；不创建第二份相同文档。

## 模板索引

| 文件（均在 assets/templates/） | 用途 |
| --- | --- |
| risk-triage.md | 分开优先级、工程风险、缺陷严重度与授权 |
| change-spec.md | 用户问题、范围、状态/契约、可观察验收 |
| task-card.md | 并行实现边界与输入输出 |
| adr.md | 重要取舍和新增服务/依赖的代价 |
| api-contract.md | API 信封、身份、错误、状态、幂等 |
| ui-acceptance.md | 真实页面路径、主题、窗口、键盘、失败恢复 |
| review.md | 独立审查、零发现、保留拒收与复核 |
| evidence.json | 机器可核结构的证据清单；默认 NOT_RUN |
| release-record.md | 源提交→产物→运行环境→验证→回退 |
| incident.md | 临时恢复与根因、复发预防 |
| ai-evaluation.md | 程序可靠性和真实模型质量分层 |
| handoff.md | Codex/Claude/人工接续，不复制超长对话 |
| integration-ledger.md | 多方集成、尝试身份、共同候选与未决问题；已有任务系统时引用它 |
| agent-message.md | 跨代理提问、变更通知、结果与必要回执；可以直接使用现有评论字段 |
| project-information-map.md | 项目主记录、维护者、版本与更新入口；已有导航时补字段 |

## 项目初始化

scripts/bootstrap_project.py 只生成协作文档和事实配置，不替你选技术栈、不运行 npm/pip、不建立虚假业务代码。
默认只输出计划；--apply 才写入。minimal 创建6个入口，standard 按需增加架构、测试、工程约定、运行和发布说明。
所有既有文件保留。若路径已存在而内容不同会标记冲突并不写；项目有旧入口时手工合并真实信息。
版本命令从项目 lockfile、package scripts、构建配置中确认；null 不等于检查通过。
新应用代码按模块02的官方模板/固定依赖与首个真实纵向切片建立。

## 只读仓库快照

scripts/repo_snapshot.py 只调用固定的 git 只读子命令，不联网、不 fetch、不修改工作树，不读取 .env 或 diff 正文。
调用时关闭仓库配置的 fsmonitor 和签名展示，diff 禁用外部 diff/textconv，避免读取索引时顺带运行这些外部程序。
--days 是当前分支的提交时间窗口；不是所有分支，更不是“近7天代码已审查”。
--base 接受已确认提交，要求它是 HEAD 祖先；输出差异路径/统计。脚本不默认为 HEAD~1。
工作区不干净时记录受跟踪 diff 哈希与未跟踪文件名，不自动 add、commit 或清理。

## 证据核对

scripts/check_evidence.py 仅核 JSON 结构、候选身份、AC覆盖、必需检查、状态与产物哈希。
PASS 必须有实际观察、代码身份、可验证产物；required 检查缺失/失败/未跑/跳过不能汇总为 PASS。
skip 要说明原因。测试 collected/executed/skipped 的口径需明确；脚本只做基本自洽核查，不假定所有测试框架统计相同。
报告不能证明内容语义、账号权限、UI真实操作或镜像确已运行；这些须人工/代理按模块07核验。
默认退出码0表示结构有效，2表示结构/证据不一致；--require-pass 时非PASS也退出3。
大日志留在受控产物系统，以 immutable URL 和 SHA256 引用；脚本不下载外链也不替你信任它。

head_sha 是实际被测候选，source_state 描述执行检查时的源码状态。证据文件随后归档产生新提交时，保留原候选；归档提交另记在发布/交接记录，不把新HEAD直接填回旧测试。
--expected-head 同样传入被测候选。若后续仅归档证据，核对差异后说明等价范围；若源码、配置、测试或输入改变，重新判断并补相关验证。

## 导出到本地开发宿主

scripts/export_skill.py 默认预览，--apply 才复制到 --root 指定仓库。
--target codex 或 opencode 写 .agents/skills/software-project-collaboration；claude 写 .claude/skills/software-project-collaboration；all 或兼容别名 both 写两份相同内容。
这是兼容快照，不是两个独立维护版本；从本套源重新导出并比对哈希，遇已有不同内容拒绝覆盖。
不更改 AGENTS/CLAUDE、hooks、权限、全局配置或目标业务代码。需更新时先审 diff，人工合并冲突，不提供强制覆盖开关。
单技能保留 LICENSE.txt；OpenAI 的界面元数据仅导出 interface，当前环境的 policy 不作为跨宿主权限复制。完整安装、更新与卸载采用[分发说明](distribution.md)中的成熟安装器。

## 副本与发布检查

scripts/inspect_installation.py --root PATH 只读检查项目三处已知技能路径，报告链接、内容指纹与版本。副本差异只说明观察到漂移，不推断实际加载版本；全局安装、宿主优先级及权限另核。

scripts/prepare_repository.py --root PATH --repository OWNER/REPO --release-ref TAG 默认预览，--apply 才创建完整公开仓库候选。生成器不访问网络、不建远端、不执行 Git、不发布；所有计划先核冲突，已有不同内容不覆盖。assets/publishing 是仅发布时读取的仓库外层模板，不是普通开发上下文。

发布候选含根 README、MIT、来源说明、维护文档、CI、标准 skills 子目录及内容清单。tools/validate_repository.py 检查本套约定、链接和常见私人标记；不是通用YAML验证器或完整隐私审计。完整复核并取得已有要求的公开授权后再发布。

## 工具限制

脚本使用 Python 3.10+ 标准库。路径中的已有符号链接拒绝写入；不把路径字符串交给 shell。
这些脚本会降低记账错误，不能代替需求判断、代码审查或生产控制。

## 完整示例

- assets/examples/resource-retirement-spec.md：合成资源的退役、所有权、副本、历史和失败状态如何写成可验收spec。
- assets/examples/dictionary-contract.md：响应信封缺陷如何做最小完整修复，并区分mock页面与真实服务证据。
- assets/examples/multi-agent-information-flow.md：多个宿主在契约变化、消息确认、结果采纳和交接中维护同一项目事实。

它们用于解释写法，不代表目标项目当前合同或已授权变更。

## 工具与行为自查

运行 python3 -m unittest discover -s scripts -p 'test_*.py' 检查脚本的无覆盖、路径、候选、分发与假通过边界。使用 assets/evals/scenarios.json 做后续技能行为评估；给执行代理只传任务与原始夹具，维护者单独读取期望，避免答案泄漏。
