#!/usr/bin/env bash
set -euo pipefail

DOC_DIR="services/feature_service/docs"

echo "[1/3] 检查 feature 文档目录存在"
if [[ ! -d "${DOC_DIR}" ]]; then
  echo "[失败] 缺少目录: ${DOC_DIR}"
  exit 1
fi

echo "[2/3] 禁止 source_type 使用管道硬编码示例"
if rg -n '"source_type"[[:space:]]*:[[:space:]]*"news\|social\|onchain"' "${DOC_DIR}" >/dev/null; then
  echo "[失败] 检测到 source_type 管道硬编码（news|social|onchain），请改为 <source_name> 或单源说明。"
  rg -n '"source_type"[[:space:]]*:[[:space:]]*"news\|social\|onchain"' "${DOC_DIR}"
  exit 1
fi

echo "[3/3] 禁止 data_source 使用管道硬编码示例"
if rg -n '"data_source"[[:space:]]*:[[:space:]]*"feature_service\.news\|feature_service\.social\|feature_service\.onchain"' "${DOC_DIR}" >/dev/null; then
  echo "[失败] 检测到 data_source 管道硬编码，请改为 feature_service.<source_name>。"
  rg -n '"data_source"[[:space:]]*:[[:space:]]*"feature_service\.news\|feature_service\.social\|feature_service\.onchain"' "${DOC_DIR}"
  exit 1
fi

echo "[通过] feature 文档 source names 守卫检查完成。"
