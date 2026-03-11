# event_center_new CI 基线记录模板

记录模板（固定）：
- `date`：执行日期（`YYYY-MM-DD`）
- `command`：执行命令
- `mode`：`quick|full`
- `result`：`pass|fail`
- `commit`：执行时对应提交（短 SHA）

填写规范：
- `result` 只能填写 `pass` 或 `fail`（小写）。
- `commit` 使用 7~12 位短 SHA（示例：`73c9048`）。
- 同一 `commit` 必须同时记录 `quick` 与 `full` 两条基线结果（成对出现）。

| date | command | mode | result | commit |
|---|---|---|---|---|
| YYYY-MM-DD | `bash scripts/check_new_arch_guards.sh --event-center-quick` | `quick` | `pass` | `abcdef0` |
