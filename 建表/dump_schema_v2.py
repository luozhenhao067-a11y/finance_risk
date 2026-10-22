# -*- coding: utf-8 -*-
"""从真库重新生成 01_建表.sql(依赖序) / 02_清空表.sql / 03_插入数据.sql"""
import re
import subprocess

MYSQL = r'D:\MySQL\server\bin\mysql.exe'
DUMP = r'D:\MySQL\server\bin\mysqldump.exe'
BASE = r'D:\资料\三项\财务单据智能风险审核\建表'
ARGS = [MYSQL, '-uroot', '-pRoot@123456', '--default-character-set=utf8mb4', '-N', '-B', 'financial_risk_audit']

# 依赖序(子表在前引用父表在后)
ORDER = [
    'user', 'role', 'permission', 'user_role', 'role_permission',
    'document', 'document_item', 'attachment', 'attachment_parse_result',
    'document_snapshot',
    'risk_rule', 'risk_analysis', 'risk_item', 'risk_evidence',
    'approval_flow', 'approval_task', 'approval_opinion',
    'audit_log', 'notification', 'report',
    'expense_standard', 'vendor', 'dict',
]

def run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        raise SystemExit(p.stderr)
    return p.stdout

# ---------- 01_建表.sql ----------
header = """-- ============================================================
-- 财务单据智能风险审核系统 建表脚本 (v2, 对齐 Spec/design/契约)
-- 数据库: MySQL 8.x   字符集: utf8mb4
-- 23 张表: RBAC(5) + 单据(5) + 快照(1) + 风险(5) + 审批(3) + 日志/通知/报告(3) + 配置(3)
-- 2026-10-22 由真库 SHOW CREATE TABLE 生成
-- ============================================================

CREATE DATABASE IF NOT EXISTS `financial_risk_audit`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `financial_risk_audit`;

SET FOREIGN_KEY_CHECKS = 0;
"""
out01 = [header]
for t in ORDER:
    ddl = run(ARGS + ['-e', 'SHOW CREATE TABLE `%s`' % t])
    # -B -N 输出: 表名<TAB>CREATE TABLE ...; batch 模式换行被转义为字面 \n, 还原
    parts = ddl.split('\t', 1)
    if len(parts) > 1:
        out01.append(parts[1].replace('\\r\\n', '\n').replace('\\n', '\n').rstrip() + ';\n')
out01.append('SET FOREIGN_KEY_CHECKS = 1;\n')

with open(BASE + r'\01_建表.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out01))
print('01_建表.sql written, tables:', len(ORDER))

# ---------- 02_清空表.sql ----------
hdr2 = """-- ============================================================
-- 财务单据智能风险审核系统 清空表脚本（可重复导入, v2）
-- ============================================================

USE `financial_risk_audit`;

SET FOREIGN_KEY_CHECKS = 0;
"""
out02 = [hdr2]
for t in reversed(ORDER):
    out02.append('TRUNCATE TABLE `%s`;' % t)
out02.append('SET FOREIGN_KEY_CHECKS = 1;\n')

with open(BASE + r'\02_清空表.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out02))
print('02_清空表.sql written')

# ---------- 03_插入数据.sql ----------
hdr3 = """-- ============================================================
-- 财务单据智能风险审核系统 测试数据 (v2, 由真库 mysqldump 生成)
-- 导入顺序: 01_建表.sql -> 02_清空表.sql -> 03_插入数据.sql
-- ============================================================

USE `financial_risk_audit`;

SET FOREIGN_KEY_CHECKS = 0;
"""
data = run([DUMP, '-uroot', '-pRoot@123456', '--default-character-set=utf8mb4',
            '--no-create-info', '--skip-triggers', '--skip-comments',
            '--complete-insert', 'financial_risk_audit'] + ORDER)
data = re.sub(r'(?m)^UNLOCK TABLES;', '-- UNLOCK TABLES;', data)
data = re.sub(r'(?m)^LOCK TABLES', '-- LOCK TABLES', data)

with open(BASE + r'\03_插入数据.sql', 'w', encoding='utf-8') as f:
    f.write(hdr3 + data + '\nSET FOREIGN_KEY_CHECKS = 1;\n')
print('03_插入数据.sql written')
