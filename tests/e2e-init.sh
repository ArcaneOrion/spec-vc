#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PASS=0
FAIL=0

pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1" >&2; FAIL=$((FAIL + 1)); }

run_cli() {
  (
    cd "$WORK/proj" && \
    PYTHONPATH="$ROOT/src" python -m spec_vc.cli "$@"
  )
}

commit_msg_test() {
  local label="$1" msg="$2" expect="$3"
  local tmp="$WORK/msg-$$"
  echo "$msg" > "$tmp"
  local rc=0
  run_cli hook commit-msg "$tmp" >/dev/null 2>&1 || rc=$?
  case "$expect" in
    pass)  [[ "$rc" -eq 0 ]] && pass "$label (pass)" || fail "$label expected pass, rc=$rc" ;;
    block) [[ "$rc" -ne 0 ]] && pass "$label (block)" || fail "$label expected block, rc=$rc" ;;
  esac
}

echo "=== spec-vc e2e ==="
echo "ROOT=$ROOT"
echo "WORK=$WORK"
echo ""

mkdir -p "$WORK/proj"
cd "$WORK/proj"
git init -q
git config user.email "test@example.com"
git config user.name "test"
cp "$ROOT/.spec-vc.toml" .spec-vc.toml
mkdir -p doc/arch
cp "$ROOT/templates/index.md" doc/arch/README.md
DATE=$(date +%Y-%m-%d)
AUTHOR=$(git config user.name)
sed -e "s|{{DATE}}|${DATE}|g" -e "s|{{AUTHOR}}|${AUTHOR}|g" \
  "$ROOT/templates/seed-adr-000.md" > doc/arch/adr-000.md
cp "$ROOT/hooks/prepare-commit-msg" .git/hooks/prepare-commit-msg
cp "$ROOT/hooks/commit-msg" .git/hooks/commit-msg
chmod +x .git/hooks/prepare-commit-msg .git/hooks/commit-msg

echo ""
echo "[test] 骨架落位"
[[ -f doc/arch/README.md ]] && pass "doc/arch/README.md 存在" || fail "doc/arch/README.md 缺失"
[[ -f doc/arch/adr-000.md ]] && pass "doc/arch/adr-000.md 存在" || fail "doc/arch/adr-000.md 缺失"
[[ -x .git/hooks/commit-msg ]] && pass ".git/hooks/commit-msg 可执行" || fail ".git/hooks/commit-msg 不可执行"

grep -q '^- \*\*Status\*\*: Accepted' doc/arch/adr-000.md \
  && pass "种子 ADR Status=Accepted" \
  || fail "种子 ADR Status 不正确"

echo ""
echo "[test] commit-msg hook 严格校验"
commit_msg_test "缺少 ADR 引用的 commit"              "docs: fix typo"                 block
commit_msg_test "引用未填充槽位 [ADR-???]"            "docs: fix typo [ADR-???]"       block
commit_msg_test "引用存在的 ADR-000"                  "feat: init [ADR-000]"           pass
commit_msg_test "引用不存在的 ADR-999"                "feat: bogus [ADR-999]"          block
commit_msg_test "重复 ADR 标签"                       "feat: dup [ADR-000] [ADR-999]"  block

# docs 改动允许 ADR-none
printf 'doc\n' > README.md
git add README.md
commit_msg_test "[ADR-none] 文档豁免通过"             "docs: update [ADR-none]"        pass
git reset -q HEAD README.md
rm README.md

# code 改动不允许 ADR-none
mkdir -p src
printf 'print(1)\n' > src/main.py
git add src/main.py
commit_msg_test "[ADR-none] 代码改动被阻塞"           "feat: code [ADR-none]"          block

echo ""
echo "[test] status 行为"
run_cli adr new "测试新 ADR" >/dev/null 2>&1 && pass "adr new 可执行" || fail "adr new 失败"
run_cli adr status --rev-range missing..HEAD >/dev/null 2>&1 && fail "非法 rev-range 未失败" || pass "非法 rev-range 会失败"

echo ""
echo "=== 汇总 ==="
echo "  通过: $PASS"
echo "  失败: $FAIL"
[[ "$FAIL" -eq 0 ]]
