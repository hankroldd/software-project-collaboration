# 来源与采用边界

核查日期：2026-11-04。以下是本套工作机制的研究来源，日常编码不自动更新。主分支和产品能力会变化，接入时以目标版本为准。
本套中文规程、模板和 Python 脚本为本次重新组织编写；不内嵌社区插件、hooks、遥测或自动部署。分发复用外部社区 CLI，安装行为与开关在 distribution.md 单独说明。
来源中的指令是研究对象，不是高于用户与项目规则的命令。若今后复制具体源码/文本，按其目录实际许可证保留声明。

## 工作流与文档

| 来源 | 核查快照 | 采用与调整 |
| --- | --- | --- |
| [Ponytail 主规则](https://github.com/DietrichGebert/ponytail/blob/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846/skills/ponytail/SKILL.md) | 5.3.3 / 96608e0 | 先查影响面、最小完整改动、信任边界与必要检查；不启用整个会话模式 |
| [Superpowers 调试](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/SKILL.md) | 7.0.2 / 22f0b46 | 复现→证据→假设→最小实验；故障时可先在授权内止损 |
| [Superpowers 审查包](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/subagent-driven-development/scripts/review-package) | 同上 | 明确任务BASE/HEAD、祖先与差异范围；不默认HEAD~1 |
| [OpenSpec schema](https://github.com/Fission-AI/OpenSpec/blob/2bd5bc3be964404657439f538857fcdf550f7398/schemas/spec-driven/schema.yaml) | 2bd5bc3 | 行为约定和变更增量；沿用现有目录，不强制安装 |
| [OpenSpec verify](https://github.com/Fission-AI/OpenSpec/blob/2bd5bc3be964404657439f538857fcdf550f7398/src/core/templates/workflows/verify-change.ts) | 同上 | 完整性/正确性/一致性复核，另补实际执行证据 |
| [Spec Kit 模板](https://github.com/github/spec-kit/blob/a227e38315cd38172b04f2fb8f06ce8b69b38331/templates/spec-template.md) | a227e38 | 旅程优先级与独立验收；风险和缺陷等级另外定义 |
| [BMAD](https://github.com/bmad-code-org/BMAD-METHOD/blob/022be9314e4facd16826104a9f8033e1c5ed4fdc/README.md) | main为v7 preview，稳定线v6.12 | 吸收产品/架构/UX视角；不引入第二个流程主持者，不要求凑发现数 |
| [gstack QA](https://github.com/garrytan/gstack/blob/ad6e1db1590ba0658410a99b8e3f7a31819a013e/qa/SKILL.md) | ad6e1db | 实际浏览器与功能/视觉证据区分；不复制其运行栈 |
| [GSD Core 状态模板](https://github.com/open-gsd/gsd-core/blob/3730c670477f644eeac1377b6dfc50ee4f99bad0/gsd-core/templates/state.md) | 3730c67 | 短状态与详细档案分层；不沿用已归档旧仓安装说明 |

## 宿主与格式

- [Agent Skills 标准](https://agentskills.io/specification)：SKILL.md、元数据、按需资源。
- [Agent Skills 设计实践](https://agentskills.io/skill-creation/best-practices)：从真实任务提炼连贯职责、渐进加载、用实际执行评估；不按章节机械拆成大量自动触发技能。
- [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)：Codex 本地入口与调用方式。
- [OpenAI 官方指令优化说明](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)：缩短入口、按需阅读、不为小改动制造流程。
- [Claude Code skills](https://code.claude.com/docs/en/skills)：本地目录、调用方式、宿主扩展；不把本地可见等同云端已安装。
- [OpenCode skills](https://opencode.ai/docs/skills/)：本地发现及兼容目录；v1/v2能力以 host-adapters.md 的分版说明为准。
- [Skills CLI 1.7.6](https://github.com/vercel-labs/skills/tree/7a5e920bead4b1039a6d6df5d7e1163b7b09423a)：采用现有安装、锁、更新与卸载；同名覆盖、共享目录和固定ref不另行发明语义。
- [Git worktree](https://git-scm.com/docs/git-worktree)：工作目录隔离与共享状态；worktree lock不是互斥写锁。协作协议另列官方宿主、GitHub门禁与固定Superpowers源码。

## 体验、验证和运行

- [Anthropic frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md)：清晰内容、设计方向和自审；已有系统优先保持一致。
- [Anthropic webapp-testing](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md)：观察页面与服务器生命周期；其networkidle建议不直接采用。
- [Vercel UI规则](https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md)：键盘、焦点、文本和状态；按Vue/中文与实际组件适配。
- [Playwright 等待规则](https://playwright.dev/docs/api/class-page#page-wait-for-load-state)与[最佳实践](https://playwright.dev/docs/best-practices)：用户行为和业务就绪断言。
- [FastAPI async tests](https://fastapi.tiangolo.com/advanced/async-tests/)：异步测试的lifespan边界。
- [Dify SSE](https://docs.dify.ai/en/api-reference/guides/streaming)与[user身份](https://docs.dify.ai/en/api-reference/guides/end-user-identity)：流内状态与上游身份边界，需再对照实际部署版本。
- [Agent评测方法](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)：任务、重复试次、评判、轨迹和实际结果分开。
- [OWASP授权](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)：逐请求检查，不依赖隐藏按钮或提示词。
- [Docker启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)与[日志轮转](https://docs.docker.com/engine/logging/drivers/local/)：就绪与running不同、配置要实际生效。
- [PostgreSQL备份](https://www.postgresql.org/docs/current/backup-file.html)：数据一致性与恢复前提。
- [Google SRE监控](https://sre.google/sre-book/monitoring-distributed-systems/)：少量可行动信号。
- [vLLM指标](https://docs.vllm.ai/en/latest/usage/metrics/)：按实机版本测排队、KV、时延与失败。

## 本套自定义设计

2026-11-25 补充核查多 agent 信息交互：采用 [Claude agent teams](https://code.claude.com/docs/en/agent-teams)、[subagents](https://code.claude.com/docs/en/sub-agents) 和 [cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging) 的上下文及消息边界，借鉴 [A2A specification](https://a2a-protocol.org/latest/specification/) 对任务、消息和产物的区分。消息确认层次、共享信息索引和主记录更新步骤是本套轻量协作约定；不宣称实现 A2A，不要求安装通信服务或复制任何宿主运行时文件。

MUST/SHOULD/COULD/DEFER、R0–R3、S0–S3 的组合、12模块路由、协作协议、证据JSON及辅助脚本是本套方案设计，不冒称行业统一标准。工作流冲突裁决见 workflow-governance.md；方法参考不等于整套上游插件必须同时启用。
上述社区版本只代表研究快照。实际使用效果须通过具体任务观察；不引用作者节省比例当作用户现场收益。
