# New Arch Guards Help Snapshot Runbook

更新时间：2026-03-12

## 1. 目的

当 `tools/local/check_new_arch_guards.sh --help` 输出发生变化时，及时刷新快照并保持守卫通过，避免“文档说明已变但快照未更新”。

相关文件：
- 脚本：`tools/local/check_new_arch_guards.sh`
- 快照：`docs/new_arch_guards_help_snapshot.txt`
- 守卫：`tools/local/check_new_arch_guards_help_snapshot_guard.sh`

## 2. 触发条件

出现以下任一情况时，需要刷新快照：
- `check_new_arch_guards.sh` 新增/删除参数
- `--help` 文案改动（用法、说明、顺序）
- 守卫关键项改动（如新前置守卫或参数说明）

## 3. 标准流程

1. 生成最新帮助输出并覆盖快照：

```bash
bash tools/local/check_new_arch_guards.sh --help > docs/new_arch_guards_help_snapshot.txt
```

2. 运行快照守卫：

```bash
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
```

3. 运行快速验证：

```bash
bash tools/ci/verify_quick.sh
```

4. 提交文件：
- `tools/local/check_new_arch_guards.sh`（如果有改动）
- `docs/new_arch_guards_help_snapshot.txt`
- `tools/local/check_new_arch_guards_help_snapshot_guard.sh`（如果有改动）
- 相关索引文档（如 `docs/CONTRACT_INDEX.md` / `docs/contracts/CONTRACTS_QUICK_REF.md`）

## 4. 常见失败与处理

1. 守卫报 `--help 输出与快照不一致`
- 按第 3 节第 1 步刷新快照，再次执行守卫。

2. 守卫报 `快照缺少关键项`
- 检查 `tools/local/check_new_arch_guards_help_snapshot_guard.sh` 中关键项列表是否已同步到 `--help`。
- 若关键项策略变更，先更新守卫，再刷新快照。

3. quick 失败但快照守卫通过
- 这是其他守卫失败，按 `verify_quick.sh` 输出定位，不应回退快照。

4. docs bundle 中 contract bundle 守卫触发不符合预期
- 先执行：
  `bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`
- 查看 `BASE_REF/HEAD` 下的四组版本探测值（`CONTRACT_INDEX` / `manifest` / `version.py` / `runtime.md`）是否真实发生变化，再决定是否补齐联动四件套。

## 5. 维护约束

- 不要手工“微调”快照内容；始终用 `--help` 输出重定向生成。
- 改动 `check_new_arch_guards.sh` 时，默认同时检查并更新该快照。
- 守卫关键项应聚焦稳定入口，避免把临时文案写入强约束。
