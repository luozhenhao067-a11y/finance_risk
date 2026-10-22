# -*- coding: utf-8 -*-
"""从 financial_risk_audit 真实库导出表结构 JSON,供 vibe coding 参考。"""
import json
import subprocess

DB = 'financial_risk_audit'
MYSQL = r'D:\MySQL\server\bin\mysql.exe'
ARGS = [MYSQL, '-uroot', '-pRoot@123456', '--default-character-set=utf8mb4', '-B', '-N', DB]

TABLE_ORDER = [
    'user', 'role', 'permission', 'user_role', 'role_permission',
    'document', 'document_item', 'attachment', 'attachment_parse_result',
    'document_snapshot',
    'risk_rule', 'risk_analysis', 'risk_item', 'risk_evidence',
    'approval_flow', 'approval_task', 'approval_opinion',
    'audit_log', 'notification', 'report',
    'expense_standard', 'vendor', 'dict',
]

# 每张表功能描述(人工撰写,供 vibe coding 理解业务)
FUNC = {
    'user': '系统用户表。存登录账号、BCrypt密码、姓名、联系方式、部门、职位。status=1启用/0禁用。单据申请人、审批人、操作人都引用此表。种子用户11个,密码统一 Root@123456(BCrypt)。',
    'role': '角色表,RBAC。系统内置6物理角色: admin/finance_manager/finance_staff/dept_manager/employee/auditor。',
    'permission': '权限表,树形结构(parent_id自引用)。perm_type: menu菜单/button按钮/api接口。perm_code如 doc:create、risk:view。',
    'user_role': '用户-角色关联表,多对多,uk(user_id,role_id)。种子数据一个用户一个角色,但结构支持多角色。',
    'role_permission': '角色-权限关联表,多对多,uk(role_id,permission_id)。',
    'document': '财务单据主表(报销/付款申请)。doc_no规则 FYyyyyMMdd-NNN。doc_type五种: 费用报销/差旅费报销/采购付款/合同付款/借款单。状态机8态: draft草稿 -> submitted已提交 -> analyzing分析中 -> pending_approval审批中 -> (returned退回可重新提交 / rejected驳回 / approved通过 / completed完成)。version单据版本,初值1,退回重提+1,审批操作乐观锁依据。current_node当前审批节点(草稿态为NULL)。risk_level冗余整体风险等级 none/low/mid/high,risk_count冗余风险项数。delete_flag逻辑删除。total_amount=明细合计。',
    'document_item': '单据费用明细,一单1~6条。expense_type费用类型、expense_date发生日期、amount金额。amount求和=document.total_amount。invoice_no发票号(报销类 INV-8位数字)/合同号(付款类 HT-2026-4位数字),借款单无。',
    'attachment': '单据附件。file_url上传路径、upload_by上传人。parse_status: parsing解析中/parsed解析成功/failed解析失败。',
    'attachment_parse_result': '附件解析结果,每附件一条uk(attachment_id)。parse_status: parsed/failed。parse_type: ocr/structured。result_json解析出的发票/行程单/合同等结构化JSON(发票含invoice_code/invoice_no/invoice_date/amount/seller/buyer/check_status,check_status可能带WARN)。confidence置信度0~1。failed时result_json为NULL、error_msg记原因。',
    'document_snapshot': '单据不可变快照表,提交时点全量快照。uk(document_id,version)。payload JSON三部分 {document, details[], attachments[]}。immutable恒为1,只读,无UPDATE接口。退回重提version+1生成新快照,旧快照保留。',
    'risk_rule': '风险规则表,内置11条 R-01~R-10 + R-EXT。rule_type: invoice/amount/supplier/price/attachment/travel/keyword/history/budget/scope/purchase。risk_level: none/low/mid/high(R-02为blocking拦截级)。params存规则参数JSON(阈值金额/比例/天数等)。enabled=1启用。',
    'risk_analysis': '风险分析主表,每单据每版本一条,uk(document_id, doc_version)。risk_score 0-100,risk_level low/mid/high,risk_count命中风险项数。status: pending/analyzing/completed/failed。overall_level整体等级,counts风险项计数JSON,recommendation建议: pass通过/supplement补充材料/manual_review人工复核/reject_suggest建议驳回,labels风险标签JSON,trigger_type触发方式: auto/manual,triggered_by触发人,analyzed_at分析时间。summary分析摘要。',
    'risk_item': '风险项明细,一个分析可0~N条。rule_id命中规则,risk_type规则类型,risk_desc风险描述,score分值。status: open待处理/handled已处理/dismissed已驳回。handled_by/handled_at/handle_opinion处理人/时间/意见。',
    'risk_evidence': '风险证据,每条风险项0~N条。evidence_type: attachment/parse_result/text。evidence_content证据内容,source证据来源(规则引擎/发票查验/预算系统等)。attachment_id可空(证据不总关联附件)。',
    'approval_flow': '审批流主表,每提交单据一条uk(document_id)。固定3节点: 1部门经理审批 -> 2财务专员审核 -> 3财务经理复核。status: running/passed/completed/rejected/returned。current_node当前节点,start_time启动(提交)时间,end_time结束时间。',
    'approval_task': '审批任务,每流程3条(node_no 1/2/3),node_name节点名(部门经理审批/财务专员审核/财务经理复核)。task_status: pending待处理/done已处理/cancelled已取消(单据退回/驳回/完成后其余节点取消)。action审批动作: approved通过/returned退回/rejected驳回。approver_id审批人,assign_time任务到达时间,handle_time处理时间(未处理为NULL)。',
    'approval_opinion': '审批意见时间线,每个已处理任务一条。action: approve同意/return退回/reject驳回(提交类 submit/resubmit/withdraw 由服务追加)。node审批节点名。create_by审批人,create_time=handle_time。',
    'audit_log': '审计日志,全系统操作轨迹。action中文枚举: 创建单据/提交审批/风险分析完成/审批通过/退回单据/驳回单据/审批完成/生成报告/上传附件。user_id操作人,role操作人角色(取自user.position,系统操作为"系统"),trace_id全链路追踪ID,user_agent客户端UA,ip来源IP。document_id可空。',
    'notification': '站内通知。type: approval审批/risk风险/system系统。is_read=0未读/1已读。审批流转(待审批提醒、退回、驳回、通过)、高风险提醒都发通知。',
    'report': '风险审核报告,每completed单据一条uk(document_id)。report_no规则 RPT-yyyyMMdd-xxxx。risk_level与risk_analysis一致。conclusion审核结论,summary报告摘要,suggestion管理建议。content JSON八部分: conclusion/summary/overall(整体风险等级与计数)/amount_checks(单据金额与解析金额核对,含合计行)/risk_items(风险项清单)/evidences(证据)/vendor(供应商核验)/suggestion/reviews(审批意见时间线)。export_file_path导出文件路径。report_status: generated/published。create_by生成人。',
    'expense_standard': '费用报销标准表。category费用类别: 住宿/交通/餐饮。city城市(通用=不限城市)。position_level职级: 员工/经理。amount标准金额,unit计量: 晚/天/人。uk(category,city,position_level)。R-03超标判断依据。',
    'vendor': '供应商档案表。name供应商名,score评分0-100,risk_level风险等级 low/mid/high,blacklist黑名单 0否/1是,established_date成立日期,note备注(经营异常等)。uk(name)。R-EXT供应商核验依据。',
    'dict': '数据字典表。dict_type字典类型: doc_type单据类型/expense_type费用类型。dict_label显示名,dict_value存储值。scope适用单据类型,空=全部(expense_type按单据类型分组,同值可出现在多个scope,如"设备采购"属于费用报销和采购付款)。sort排序,enabled启用。uk(dict_type,scope,dict_value)。',
}

# 业务补充说明(附在每表后)
NOTES = {
    'document': [
        '状态流转: draft --提交--> submitted --自动分析--> analyzing --分析完成--> pending_approval --三节点全通过--> approved --生成报告--> completed ; pending_approval --节点退回--> returned(修改后重新提交,version+1) ; pending_approval --驳回--> rejected(终态)',
        'draft 状态无 approval_flow/risk_analysis/notification',
        'returned 状态: flow.status=returned, 退回节点 task=done(action=returned), 后续节点 task=cancelled',
        'completed 状态必有 report 一条',
        '乐观锁: 审批/退回操作带 version,UPDATE ... WHERE id=? AND version=?,不符返回40903',
    ],
    'document_snapshot': [
        '提交时生成快照: 记录提交时点单据头、明细、附件全量数据,审批中不可变',
        '退回重提 version+1,提交时再生成新快照,uk(document_id,version) 保证每版本一条',
    ],
    'approval_flow': [
        '节点顺序固定: 1部门经理审批(申请人部门经理) -> 2财务专员审核(财务部) -> 3财务经理复核(财务经理)',
        'returned: end_time=退回时间, current_node=退回节点',
        'rejected/passed: end_time=节点3处理时间, current_node=3',
    ],
    'approval_task': [
        'assign_time规则: 节点1=submit_time; 后续节点=前一节点handle_time; 流程结束时未到达节点=submit_time(任务预建)',
        'handle_time晚于assign_time(保证时间合理)',
    ],
    'risk_analysis': [
        'risk_score=所有risk_item.score最大值(无风险项时按单据算出低分)',
        'risk_level由最高风险项等级决定',
        'analysis_no规则 RAyyyyMMdd-NNN',
        '退回重提后同单据生成新版本分析,uk(document_id,doc_version) 保证每版本一条',
    ],
}

def run(sql):
    p = subprocess.run(ARGS + ['-e', sql], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        raise SystemExit('mysql error: ' + p.stderr)
    return p.stdout


def main():
    # 表注释
    tcomment = {}
    for line in run("SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA='financial_risk_audit'").splitlines():
        parts = line.split('\t')
        tcomment[parts[0]] = parts[1] if len(parts) > 1 else ''

    # 列
    cols = {}
    for line in run("SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, "
                    "COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT "
                    "FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA='financial_risk_audit' "
                    "ORDER BY TABLE_NAME, ORDINAL_POSITION").splitlines():
        parts = line.split('\t')
        t = parts[0]
        cols.setdefault(t, []).append({
            'name': parts[1],
            'type': parts[2],
            'nullable': parts[3] == 'YES',
            'key': parts[4],            # PRI/UNI/MUL/空
            'default': None if parts[5] == 'NULL' else parts[5],
            'extra': parts[6],
            'comment': parts[7] if len(parts) > 7 else '',
        })

    # 索引
    idx = {}
    for line in run("SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME "
                    "FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA='financial_risk_audit' "
                    "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX").splitlines():
        parts = line.split('\t')
        t = parts[0]
        idx.setdefault(t, {}).setdefault(parts[1], {'unique': parts[2] == '0', 'columns': []})
        idx[t][parts[1]]['columns'].append(parts[4])

    tables = []
    for t in TABLE_ORDER:
        tables.append({
            'name': t,
            'comment': tcomment.get(t, ''),
            'function': FUNC.get(t, ''),
            'business_notes': NOTES.get(t, []),
            'columns': cols.get(t, []),
            'indexes': [{'name': k, 'unique': v['unique'], 'columns': v['columns']}
                        for k, v in idx.get(t, {}).items()],
        })

    doc = {
        'database': DB,
        'charset': 'utf8mb4',
        'engine': 'InnoDB',
        'version': 'MySQL 8.x',
        'generated_at': '2026-10-22',
        'purpose': '财务单据智能风险审核系统核心库。覆盖: 用户权限(RBAC)、财务单据与费用明细、附件与OCR解析、提交快照、风险规则与智能风控分析、三级审批流(部门经理审批-财务专员审核-财务经理复核)、审计日志、站内通知、审核报告、费用标准/供应商/字典配置。',
        'table_count': len(tables),
        'tables': tables,
    }

    out = r'D:\资料\三项\财务单据智能风险审核\项目信息\看表结构\数据库表结构说明.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print('written:', out)
    print('tables:', len(tables), 'columns:', sum(len(t['columns']) for t in tables))


if __name__ == '__main__':
    main()
