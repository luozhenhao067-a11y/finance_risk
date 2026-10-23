# 财务单据智能风险审核系统 — 后端

基于 FastAPI + Uvicorn + SQLAlchemy 2.0 + MySQL 8 实现的接口服务，接口契约见
`../项目信息/财务单据智能风险审核系统-接口契约.md`。

## 快速开始

```bash
cd back_endpoint
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python run.py
```

- 服务地址：`http://127.0.0.1:8000`
- 健康检查：`GET http://127.0.0.1:8000/api/v1/health`
- 接口文档：`http://127.0.0.1:8000/docs`
- 启动时自动执行幂等迁移（`app/migrate.py`），并创建 `storage/files`、`storage/exports` 目录。

> **必须单进程运行**：登录失败计数与后台任务均依赖进程内状态，禁止 `--workers > 1`。

## 配置

默认配置位于 `app/config.py`，可用环境变量覆盖同名项（大写）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_USER` / `DB_PASSWORD` | `root` / `Root@123456` | MySQL 账号 |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | MySQL 地址 |
| `DB_NAME` | `financial_risk_audit` | 数据库名 |
| `JWT_SECRET` | 内置开发密钥 | 生产环境必须替换 |
| `JWT_EXPIRE_MINUTES` | `120` | Token 有效期 |
| `STORAGE_DIR` | `back_endpoint/storage` | 附件根目录 |
| `MAX_UPLOAD_BYTES` | `20971520` | 单附件上限 20MB |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:4173` | 前端开发地址 |
| `AI_API_KEY` | 空 | 大模型 Key；**留空则所有 AI 能力使用规则/Mock 兜底** |
| `AI_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容接口地址 |
| `AI_MODEL` | `deepseek-chat` | 文本模型 |
| `AI_VISION_MODEL` | 空 | 多模态模型；留空则附件解析走 Mock |
| `AI_VISION_API_KEY` / `AI_VISION_BASE_URL` | 空 | 视觉模型独立凭据，留空复用文本模型配置 |
| `AI_TIMEOUT_SECONDS` | `30` | 单次模型调用超时 |
| `AI_MAX_TOKENS` / `AI_TEMPERATURE` | `1024` / `0.2` | 生成参数 |
| `AI_MAX_PAGES` | `2` | PDF 最多渲染前 N 页送视觉模型 |

AI 配置单独放在 `back_endpoint/.env`（模板见 `.env.example`，已被 `.gitignore` 忽略）。
未配置 `AI_API_KEY` 时不发起任何外部请求，发票/行程单解析、风险语义判断、报告摘要、
智能问答全部走确定性兜底，前后端联调与演示不受影响。

## 目录结构

```
back_endpoint/
├── run.py                  # uvicorn 启动入口
├── app/
│   ├── main.py             # 应用装配、异常处理器、路由注册
│   ├── config.py           # 配置
│   ├── database.py         # 引擎与会话
│   ├── migrate.py          # 启动幂等迁移
│   ├── models/             # 23 张表 ORM
│   ├── schemas/            # Pydantic 请求体
│   ├── core/               # 信封、错误码、鉴权、trace、权限矩阵
│   ├── utils/              # 分页、编号、时间、金额、存储、CSV
│   ├── services/           # 业务事务层（ai_client / ai_parser / risk_engine / ai_qa_service）
│   └── routers/            # 薄路由层（含 ai_chat.py 智能问答）
├── engine/                 # 风险规则引擎（独立包）
│   ├── base.py             # 上下文与结果结构
│   ├── registry.py         # 规则注册表
│   ├── engine.py           # 分析编排（先传统规则，后 AI 增强规则）
│   └── rules/              # R-01/R-05/R-07/R-09/R-10/R-11/R-12
├── migrate/001_add_project_dept.sql  # 迁移留档
└── scripts/smoke.py        # 端到端冒烟脚本
```

## 统一约定

- 所有接口前缀 `/api/v1`。
- 业务响应统一信封：`{ "code": 0, "message": "success", "data": ..., "trace_id": "..." }`。
- 业务错误返回 HTTP 200 + 非 0 `code`；未认证返回 HTTP 401；二进制/流式响应不包信封。
- `Authorization: Bearer <token>`；JWT 有效期 2 小时。
- 时间格式 `yyyy-MM-dd HH:mm:ss`；金额保留 2 位小数。
- 分页 `{ total, page, page_size, list }`，`page` 从 1 开始，`page_size` 上限 100。

错误码：`40001` 校验失败、`40101` 未认证、`40102` 账号或密码错误、`40103` 登录锁定、
`40301` 无权限、`40302` 越数据范围、`40401` 单据不存在、`40402` 附件不存在、
`40404` 快照/报告/规则不存在、`40901` 非法状态流转、`40902` 任务已处理、`40903` 版本冲突。

## 核心链路

提交链（`BackgroundTasks` 进程内异步）：

```
draft --submit--> submitted --start_analysis--> analyzing --finish_analysis--> pending_approval
                     \-- 附件解析 / 规则分析（失败重试 3 次后仍进入 pending_approval）
```

审批固定三节点：部门经理审批 → 财务专员审核 → 财务经理复核。
末节点通过后单据进入 `approved`，同事务自动生成风险审核报告；财务确认完成后进入 `completed`。

已实现规则：

| 规则 | 名称 | 等级 | 说明 |
| --- | --- | --- | --- |
| R-01 | 金额一致性 | high | 发票解析金额合计 vs 单据金额（容差 0.01） |
| R-05 | 费用标准 | mid | 差旅住宿/交通/餐饮按城市、职级、天数比对 |
| R-07 | 消费异常 | mid | 周末消费、连号发票、单日多票（种子默认停用） |
| R-09 | 附件完整性 | low | 解析置信度低于阈值、必需附件缺失 |
| R-10 | 重复票据 | high | 同一发票号在其他有效单据中出现 |
| R-11 | 主体名称语义一致性 | high | AI 语义比对合同乙方、发票抬头、付款对象，兜底为名称归一化规则 |
| R-12 | 消费异常智能检测 | mid | AI 结合金额/类型/城市/历史均值判断，兜底为 1.5 倍历史均值阈值 |

规则开关与阈值可通过 `PUT /api/v1/admin/risk-rules/{code}` 调整。

### AI 增强接口

- `POST /api/v1/documents/{doc_id}/ai-qa`：请求体 `{"question": "这张单为什么被标记为高风险？"}`，
  响应 `data` 为 `{"answer": "...", "related_risk_codes": ["R-01"]}`。需登录且具备单据查看权限。
- 附件解析在提交链 `BackgroundTasks` 中自动执行；`parse_type` 为 `ai` 表示视觉模型识别，
  `ocr` 表示 Mock 兜底。

## 冒烟测试

```bash
# 终端 1
python run.py
# 终端 2
python scripts/smoke.py
```

脚本会走完登录、建单、提交、三节点审批、报告、风险中心、日志、管理端与工作台统计。

## 前端联调

```bash
cd ../fronted
VITE_USE_MOCK=false VITE_API_BASE=http://127.0.0.1:8000/api/v1 npm run dev
```

种子账号密码均为 `Root@123456`：`zhaolei`（申请人）、`liuyang`（部门经理）、
`lina`（财务专员）、`zhangwei`（财务经理）、`admin`（管理员）。

## 已知边界

- 附件解析为确定性模拟（按文件名生成 OCR 字段与置信度），不接入真实 OCR。
- 后端仅实现前端实际接线端点与契约 §6 规划端点；明细增量 CRUD、用户/部门/审批流写操作未实现。
- 无部门表，`dept_id` 由部门名 MD5 生成伪 ID；单据部门取自 `user.department`。
