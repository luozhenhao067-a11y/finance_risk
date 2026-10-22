# -*- coding: utf-8 -*-
"""迁移第二步: 快照 payload / 报告 content JSON / 新表种子数据。
读真库, 生成 SQL 并执行。依赖 migrate_v2.sql 已执行。"""
import json
import subprocess

MYSQL = r'D:\MySQL\server\bin\mysql.exe'
ARGS = [MYSQL, '-uroot', '-pRoot@123456', '--default-character-set=utf8mb4', '-B', '-N', 'financial_risk_audit']


def run(sql):
    p = subprocess.run(ARGS + ['-e', sql], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        raise SystemExit('mysql error: ' + p.stderr)
    return p.stdout


def q(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace('\\', '\\\\').replace("'", "''") + "'"


def rows(sql):
    out = run(sql)
    return [line.split('\t') for line in out.splitlines() if line.strip()]


# ---------- 1. 快照 ----------
docs = rows("""
SELECT d.id, d.doc_no, d.title, d.total_amount, d.version, d.submit_time
FROM document d JOIN approval_flow f ON f.document_id = d.id
""")
details = rows("SELECT document_id, expense_type, expense_date, amount, invoice_no FROM document_item")
atts = rows("SELECT document_id, file_name, file_type, file_size FROM attachment")

snap_rows = []
for d in docs:
    doc_id, doc_no, title, total, version, submit_time = d
    payload = {
        'document': {'doc_no': doc_no, 'title': title, 'total_amount': float(total), 'submit_time': submit_time},
        'details': [{'expense_type': r[1], 'expense_date': r[2], 'amount': float(r[3]), 'invoice_no': r[4]}
                    for r in details if r[0] == doc_id],
        'attachments': [{'file_name': r[1], 'file_type': r[2], 'file_size': int(r[3])}
                        for r in atts if r[0] == doc_id],
    }
    snap_rows.append((doc_id, int(version), json.dumps(payload, ensure_ascii=False), submit_time or '2026-10-01 00:00:00'))

# ---------- 2. 报告 content ----------
reports = rows("SELECT id, document_id, risk_level, conclusion, summary, suggestion FROM report")
items = rows("""
SELECT a.document_id, r.rule_code, i.risk_level, i.risk_desc, i.risk_type, i.score
FROM risk_item i
JOIN risk_analysis a ON a.id = i.analysis_id
JOIN risk_rule r ON r.id = i.rule_id
""")
evidences = rows("""
SELECT a.document_id, e.evidence_content
FROM risk_evidence e
JOIN risk_item i ON i.id = e.risk_item_id
JOIN risk_analysis a ON a.id = i.analysis_id
""")
opinions = rows("""
SELECT t.document_id, u.real_name, o.opinion, o.create_time
FROM approval_opinion o
JOIN approval_task t ON t.id = o.task_id
LEFT JOIN user u ON u.id = o.create_by
""")
doc_items = rows("SELECT document_id, expense_type, amount FROM document_item")

LEVEL_TEXT = {'high': '高风险', 'mid': '中风险', 'low': '低风险'}
report_updates = []
for r in reports:
    rid, doc_id, rlevel, conclusion, summary, suggestion = r
    level = 'mid' if rlevel == 'medium' else rlevel
    doc_its = [x for x in items if x[0] == doc_id]
    counts = {'high': 0, 'mid': 0, 'low': 0}
    for x in doc_its:
        counts[x[2]] = counts.get(x[2], 0) + 1
    amount_checks = [{'name': x[1], 'doc_amount': float(x[2]), 'parsed_amount': float(x[2]),
                      'diff': 0, 'conclusion': '一致'} for x in doc_items if x[0] == doc_id]
    total = sum(c['doc_amount'] for c in amount_checks)
    if amount_checks:
        amount_checks.append({'name': '合计', 'doc_amount': total, 'parsed_amount': total,
                              'diff': 0, 'conclusion': '一致', 'is_total': True})
    reviews = [{'name': x[1], 'role': '审批人', 'content': x[2], 'created_at': x[3]}
               for x in opinions if x[0] == doc_id]
    content = {
        'conclusion': conclusion,
        'summary': summary,
        'overall': {'level': level,
                    'text': '整体风险：%s（%d 项：高 %d · 中 %d · 低 %d）' % (
                        LEVEL_TEXT.get(level, '无风险'),
                        counts['high'] + counts['mid'] + counts['low'],
                        counts['high'], counts['mid'], counts['low'])},
        'amount_checks': amount_checks,
        'risk_items': [{'rule_code': x[1], 'level': x[2], 'title': x[3], 'basis': x[4]} for x in doc_its],
        'evidences': [{'snippet': x[1]} for x in evidences if x[0] == doc_id],
        'vendor': None,
        'suggestion': suggestion,
        'reviews': reviews,
    }
    report_updates.append("UPDATE `report` SET `content` = %s WHERE `id` = %s;"
                          % (q(json.dumps(content, ensure_ascii=False)), rid))

# ---------- 3. 新表种子 ----------
standards = [
    ('住宿', '北京', '员工', 500.00, '晚'), ('住宿', '北京', '经理', 800.00, '晚'),
    ('住宿', '上海', '员工', 450.00, '晚'), ('住宿', '广州', '员工', 400.00, '晚'),
    ('住宿', '深圳', '员工', 450.00, '晚'),
    ('餐饮', '通用', '员工', 150.00, '人'), ('餐饮', '通用', '经理', 300.00, '人'),
    ('交通', '通用', '员工', 500.00, '天'), ('交通', '通用', '经理', 800.00, '天'),
]
vendors = [
    ('华信商贸有限公司', 40, 'high', 1, '2020-03-15', '工商状态经营异常,黑名单'),
    ('北京云启科技有限公司', 85, 'low', 0, '2019-06-01', None),
    ('京东企业购', 90, 'low', 0, '2015-01-01', None),
    ('智汇咨询(深圳)有限公司', 75, 'mid', 0, '2021-11-20', None),
    ('星辰科技有限公司', 80, 'low', 0, '2016-08-08', '公司主体'),
]
dicts = [('doc_type', v, v, '', i + 1) for i, v in enumerate(
    ['费用报销', '差旅费报销', '采购付款', '合同付款', '借款单'])]
expense_sets = {
    '费用报销': ['办公费', '场地费', '设备采购', '其他'],
    '差旅费报销': ['交通费', '住宿费', '餐饮费', '其他'],
    '采购付款': ['设备采购', '合同款', '服务费', '其他'],
    '合同付款': ['合同款', '服务费', '其他'],
    '借款单': ['借款'],
}
for dt, vals in expense_sets.items():
    for i, v in enumerate(vals):
        dicts.append(('expense_type', v, v, dt, i + 1))

def ins(table, cols, data):
    head = "INSERT INTO `%s` (%s) VALUES\n" % (table, ', '.join('`%s`' % c for c in cols))
    body = ',\n'.join('(' + ', '.join(q(v) for v in r) + ')' for r in data)
    return head + body + ';\n'

sql = []
sql.append('USE `financial_risk_audit`;\nSET FOREIGN_KEY_CHECKS = 0;\n')
# 幂等: 清空后重插
for t in ('document_snapshot', 'expense_standard', 'vendor', 'dict'):
    sql.append('DELETE FROM `%s`;\nALTER TABLE `%s` AUTO_INCREMENT = 1;' % (t, t))
sql.append(ins('document_snapshot',
               ['document_id', 'version', 'payload', 'created_at'], snap_rows))
sql.append(ins('expense_standard',
               ['category', 'city', 'position_level', 'amount', 'unit'], standards))
sql.append(ins('vendor', ['name', 'score', 'risk_level', 'blacklist', 'established_date', 'note'], vendors))
sql.append(ins('dict', ['dict_type', 'dict_label', 'dict_value', 'scope', 'sort'], dicts))
sql.extend(report_updates)
sql.append('SET FOREIGN_KEY_CHECKS = 1;\n')

with open(r'D:\资料\三项\财务单据智能风险审核\建表\migrate_v2_data.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(sql))

p = subprocess.run(ARGS, stdin=open(r'D:\资料\三项\财务单据智能风险审核\建表\migrate_v2_data.sql', encoding='utf-8'),
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
if p.returncode != 0:
    raise SystemExit('execute error: ' + p.stderr)

print('snapshots:', len(snap_rows), 'reports:', len(report_updates),
      'standards:', len(standards), 'vendors:', len(vendors), 'dicts:', len(dicts))
