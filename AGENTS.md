# Agent continuation instructions

This repository implements the user-approved AI digital talent platform. Before editing, read docs/DEVELOPMENT_HANDOFF.md, .execution/progress.md, and the detailed plan at D:/Obsidian仓库/Obsidian/项目/AI数字化人才平台项目/开发计划-2026-11-05/AI数字化人才平台-详细开发todolist.md.

- Inspect git status and diff; preserve uncommitted work. Do not reset, clean, or overwrite it from stale staging.
- The handoff records the last verified checkpoint; inspect actual code and rerun the relevant checks before claiming completion.
- Keep the plan, a current handoff checkpoint and per-task verification evidence updated at each completed task, material failure or intentional stop. Do not put secrets in records.
- User authorized development and local reversible checks. Do not repeatedly ask permission for that scope. Do not deploy, push, send external recruitment email, or configure paid/model credentials without the relevant user authorization.
- Latest model intent and credential-source authorization are recorded in docs/MODEL_AND_DATABASE_DECISION.md. User selected DeepSeek deepseek-flash and DashScope embedding/rerank. Await DeepSeek official key or an explicit proxy-channel choice. DashScope Beijing endpoint was found in the additionally authorized rag_examples code; validate it at integration time instead of asking for its region again. Do not repeat resolved questions, send proxy keys to another host, copy whole old env files, or scan other credential locations.
- Local .env and .execution/local-accounts.json contain generated project credentials. Never print, commit or copy them into documentation. Do not touch other projects' containers or databases.
- SQL migrations/destructive tests run only on isolated talent_test. Preserve talent_dev and existing host databases.
- Output goes to this Obsidian project directory. The original D:/AI数字化人才平台-相关文档 is reference material and temporary staging only.
- No new features outside approved scope; training is a framework. Admin and HR remain separate; department-private exam/evaluation content never enters shared candidate profiles or embeddings.
- Continue the current task in the plan. Use meaningful RED/GREEN tests and actual dependency checks; technical probes are not a business acceptance pass.
