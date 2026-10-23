"""端到端冒烟脚本（需先启动服务：python run.py）。

用法：
    python scripts/smoke.py [base_url]

覆盖：登录、建单、提交校验、提交链、审批三节点、报告、风险中心、日志、管理端。
"""

import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000") + "/api/v1"
PASSWORD = "Root@123456"


def call(client: httpx.Client, method: str, path: str, token: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = client.request(method, f"{BASE}{path}", headers=headers, **kwargs)
    try:
        body = response.json()
    except ValueError:
        return response, None
    return response, body


def login(client: httpx.Client, username: str) -> str:
    response, body = call(client, "POST", "/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200 and body["code"] == 0, (username, body)
    print(f"[OK] login {username}: {body['data']['user']['name']} / {body['data']['user']['role']}")
    return body["data"]["token"]


def main() -> None:
    with httpx.Client(timeout=60) as client:
        response, body = call(client, "GET", "/health")
        assert body["code"] == 0, body
        print("[OK] health")

        zhaolei = login(client, "zhaolei")
        liuyang = login(client, "liuyang")
        lina = login(client, "lina")
        zhangwei = login(client, "zhangwei")
        admin = login(client, "admin")

        payload = {
            "doc_type": "差旅费报销",
            "title": "冒烟测试差旅报销",
            "dept_name": "研发部",
            "project": "冒烟测试项目",
            "details": [
                {"expense_type": "交通费", "expense_date": "2026-10-15", "amount": 1280, "invoice_no": "INV-90000001"},
                {"expense_type": "住宿费", "expense_date": "2026-10-16", "amount": 1600, "invoice_no": "INV-90000002"},
            ],
            "attachments": [{"file_name": "发票-smoke.png", "size_label": "120KB"}],
            "submit": False,
        }
        _, body = call(client, "POST", "/documents", token=zhaolei, json=payload)
        assert body["code"] == 0, body
        doc_id = body["data"]["id"]
        print(f"[OK] create draft {body['data']['doc_no']} status={body['data']['status']}")

        _, body = call(client, "POST", f"/documents/{doc_id}/submit", token=zhaolei)
        assert body["code"] == 0, body
        print(f"[OK] submit version={body['data']['version']}")

        for _ in range(20):
            _, body = call(client, "GET", f"/documents/{doc_id}", token=zhaolei)
            if body["data"]["doc"]["status"] == "pending_approval":
                break
            time.sleep(0.5)
        detail = body["data"]
        assert detail["doc"]["status"] == "pending_approval", detail["doc"]["status"]
        print(
            f"[OK] analysis done risk={detail['doc']['risk_level']} "
            f"items={len(detail['risk_items'])} flow={len(detail['approval_flow']['chain'])}"
        )

        for username, token in (("liuyang", liuyang), ("lina", lina), ("zhangwei", zhangwei)):
            _, body = call(client, "GET", "/approvals/todo", token=token)
            assert body["code"] == 0, body
            _, body = call(
                client,
                "POST",
                f"/documents/{doc_id}/approve",
                token=token,
                json={"action": "approve", "opinion": f"{username} 同意"},
            )
            assert body["code"] == 0, body
            print(f"[OK] approve by {username} -> {body['data']['doc_status']}")

        _, body = call(client, "GET", f"/documents/{doc_id}", token=zhangwei)
        assert body["data"]["doc"]["status"] == "approved", body["data"]["doc"]["status"]
        assert body["data"]["report"], "报告未自动生成"
        print(f"[OK] report {body['data']['report']['report_no']}")

        _, body = call(client, "POST", f"/documents/{doc_id}/complete", token=zhangwei)
        assert body["code"] == 0 and body["data"]["status"] == "completed", body
        print("[OK] complete")

        _, body = call(client, "GET", "/risk-items?page=1&page_size=5", token=zhangwei)
        assert body["code"] == 0, body
        _, body = call(client, "GET", "/risk-items/summary", token=zhangwei)
        print(f"[OK] risk center total={body['data']['total_items']} docs={body['data']['doc_count']}")

        _, body = call(client, "GET", "/reports?page=1&page_size=5", token=zhangwei)
        assert body["code"] == 0, body
        print(f"[OK] reports total={body['data']['total']}")

        _, body = call(client, "GET", "/logs?page=1&page_size=5", token=zhangwei)
        assert body["code"] == 0, body
        print(f"[OK] logs total={body['data']['total']}")

        _, body = call(client, "GET", "/admin/risk-rules", token=admin)
        assert body["code"] == 0, body
        print(f"[OK] admin rules={len(body['data'])}")

        _, body = call(client, "GET", "/dashboard/stats", token=zhangwei)
        assert body["code"] == 0, body
        print(f"[OK] dashboard kpis={body['data']['kpis']}")

        print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
