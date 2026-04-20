#!/usr/bin/env bash
# spec-vc · new-adr.sh
#
# 创建新的 ADR 文件,编号自动取当前最大值 + 1。
# 从 templates/adr.md 渲染,替换占位符。
#
# 使用:
#   scripts/new-adr.sh "<标题>"
#   scripts/new-adr.sh "<标题>" --template=<path>

set -euo pipefail

TITLE="${1:-}"
if [[ -z "$TITLE" ]]; then
    echo "用法: $0 \"<标题>\"" >&2
    exit 2
fi

# 解析参数
TEMPLATE=""
shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --template=*) TEMPLATE="${1#*=}" ;;
        *) echo "未知参数: $1" >&2; exit 2 ;;
    esac
    shift
done

ADR_DIR="${ADR_DIR:-doc/arch}"
SKILL_ROOT="${SKILL_ROOT:-$(dirname "$(dirname "$(realpath "$0")")")}"
TEMPLATE="${TEMPLATE:-${SKILL_ROOT}/templates/adr.md}"

if [[ ! -d "$ADR_DIR" ]]; then
    echo "[spec-vc] ADR 目录不存在,请先运行 /spec-vc adr-init" >&2
    exit 2
fi

if [[ ! -f "$TEMPLATE" ]]; then
    echo "[spec-vc] 模板文件不存在: $TEMPLATE" >&2
    exit 2
fi

# ---- 取当前最大编号 + 1 ----
MAX_ID=-1
for f in "$ADR_DIR"/adr-*.md; do
    [[ -f "$f" ]] || continue
    id=$(basename "$f" | sed -E 's/adr-([0-9]+)\.md/\1/')
    id_int=$((10#$id))  # 强制十进制,避免 007 被当八进制
    [[ $id_int -gt $MAX_ID ]] && MAX_ID=$id_int
done
NEXT_ID=$((MAX_ID + 1))
NEXT_NUM=$(printf "%03d" $NEXT_ID)

# ---- 填充模板 ----
DATE=$(date +%Y-%m-%d)
AUTHOR=$(git config user.name 2>/dev/null || echo "unknown")
OUTPUT="${ADR_DIR}/adr-${NEXT_NUM}.md"

# 用 awk 做字面替换,避免 sed 对特殊字符(/ & \ $ 等)敏感。
# 先把替换值存到环境变量,awk 通过 -v 拿到后直接 gsub 字面量。
TITLE_VAL="$TITLE" \
NUMBER_VAL="$NEXT_NUM" \
DATE_VAL="$DATE" \
AUTHOR_VAL="$AUTHOR" \
awk '
    BEGIN {
        n = ENVIRON["NUMBER_VAL"]
        t = ENVIRON["TITLE_VAL"]
        d = ENVIRON["DATE_VAL"]
        a = ENVIRON["AUTHOR_VAL"]
    }
    {
        gsub(/\{\{NUMBER\}\}/, n)
        gsub(/\{\{TITLE\}\}/,  t)
        gsub(/\{\{DATE\}\}/,   d)
        gsub(/\{\{AUTHOR\}\}/, a)
        gsub(/\{\{TAGS\}\}/,   "")
        print
    }
' "$TEMPLATE" > "$OUTPUT"

echo "[spec-vc] 已创建 $OUTPUT"
echo ""
echo "下一步:"
echo "  1. 填写 Context / Decision / Consequences"
echo "  2. 实现代码"
echo "  3. 提交时在 commit message 末尾加 [ADR-${NEXT_NUM}]"
echo ""
echo "示例 commit message:"
echo "  feat(<scope>): <subject> [ADR-${NEXT_NUM}]"
