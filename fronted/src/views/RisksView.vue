<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ShieldAlert, ShieldCheck, ShieldX, Inbox, ArrowUpRight } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { riskInfo, formatMoney } from '../utils/format'

const router = useRouter()
const store = useAppStore()

const keyword = ref('')
const levelFilter = ref('全部等级')
const statusFilter = ref('全部状态')

const RISK_STATUSES = [
  { value: 'open', label: '待处理' },
  { value: 'handled', label: '已处理' },
  { value: 'dismissed', label: '已排除' }
]

// 数据权限（Spec 4.6）：按角色过滤可见风险项
const allRisks = computed(() =>
  store.visibleRiskItems()
    .map((item) => {
      const doc = store.getDocument(item.doc_id)
      return { ...item, doc }
    })
    .filter((item) => item.doc)
    .sort((a, b) => {
      const rank = { high: 3, mid: 2, low: 1, none: 0 }
      return (rank[b.level] || 0) - (rank[a.level] || 0) || a.doc.doc_no.localeCompare(b.doc.doc_no)
    })
)

const filtered = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return allRisks.value.filter((item) => {
    const matchLevel = levelFilter.value === '全部等级' || riskInfo(item.level).text === levelFilter.value
    const matchStatus =
      statusFilter.value === '全部状态' ||
      ({ open: '待处理', handled: '已处理', dismissed: '已排除' })[item.status] === statusFilter.value
    const matchText =
      !text ||
      [item.title, item.basis, item.doc.doc_no, item.doc.title, item.doc.applicant_name].some((value) =>
        String(value || '').toLowerCase().includes(text)
      )
    return matchLevel && matchStatus && matchText
  })
})

const summary = computed(() => {
  const risks = allRisks.value
  return [
    {
      label: '识别风险项',
      value: risks.length,
      note: `关联 ${new Set(risks.map((item) => item.doc_id)).size} 张单据`,
      icon: ShieldAlert,
      color: '#2563EB',
      bg: '#EFF6FF'
    },
    {
      label: '高风险项',
      value: risks.filter((item) => item.level === 'high').length,
      note: '需优先人工复核',
      icon: ShieldX,
      color: '#DC2626',
      bg: '#FEF2F2'
    },
    {
      label: '中风险项',
      value: risks.filter((item) => item.level === 'mid').length,
      note: '建议补充材料',
      icon: ShieldAlert,
      color: '#F59E0B',
      bg: '#FFFBEB'
    },
    {
      label: '低风险项',
      value: risks.filter((item) => item.level === 'low').length,
      note: '提示性校验结果',
      icon: ShieldCheck,
      color: '#16A34A',
      bg: '#F0FDF4'
    }
  ]
})

function openRisk(item) {
  router.push(`/documents/${item.doc_id}?tab=risk`)
}
</script>

<template>
  <div class="risks-page">
    <header class="page-header">
      <div class="header-title-box">
        <h1 class="header-title">风险分析</h1>
        <div class="header-subtitle">汇总全部单据的智能风险识别结果 · 共 {{ allRisks.length }} 项风险</div>
      </div>
      <div class="header-actions">
        <div class="search-box">
          <Search :size="15" />
          <input v-model="keyword" type="text" placeholder="搜索风险项 / 单据编号" />
        </div>
        <div class="select-wrap">
          <select v-model="levelFilter" class="select" aria-label="风险等级">
            <option>全部等级</option>
            <option>高风险</option>
            <option>中风险</option>
            <option>低风险</option>
          </select>
        </div>
        <div class="select-wrap">
          <select v-model="statusFilter" class="select" aria-label="风险状态">
            <option>全部状态</option>
            <option v-for="row in RISK_STATUSES" :key="row.value" :value="row.label">{{ row.label }}</option>
          </select>
        </div>
        <button class="btn btn-outline" type="button" @click="router.push('/approvals')">
          <span>前往审批中心</span>
          <ArrowUpRight :size="15" />
        </button>
      </div>
    </header>

    <div class="page-body">
      <div class="summary">
        <div v-for="item in summary" :key="item.label" class="summary-card card">
          <div class="summary-icon" :style="{ background: item.bg, color: item.color }">
            <component :is="item.icon" :size="20" />
          </div>
          <div class="summary-text">
            <div class="summary-value" :style="{ color: item.color }">{{ item.value }}</div>
            <div class="summary-label">{{ item.label }}</div>
          </div>
          <div class="summary-note">{{ item.note }}</div>
        </div>
      </div>

      <section class="list-card card">
        <div class="list-head">
          <div class="list-title-box">
            <h2 class="section-title">风险项清单</h2>
            <span class="muted-sm">当前显示 {{ filtered.length }} 项</span>
          </div>
          <div class="level-legend">
            <span><i style="background: #dc2626"></i>高风险</span>
            <span><i style="background: #f59e0b"></i>中风险</span>
            <span><i style="background: #16a34a"></i>低风险</span>
          </div>
        </div>

        <div class="table-wrap">
          <table class="data-table risk-table">
            <thead>
              <tr>
                <th style="width: 88px">风险等级</th>
                <th style="width: 62px">规则</th>
                <th style="width: 158px">风险项</th>
                <th style="min-width: 250px">判定依据</th>
                <th style="width: 148px">关联单据</th>
                <th style="width: 150px">单据标题</th>
                <th style="width: 84px">申请人</th>
                <th style="width: 112px">单据金额</th>
                <th style="width: 82px">处理状态</th>
                <th style="width: 112px">解析置信度</th>
                <th style="width: 76px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filtered" :key="item.id">
                <td><span class="badge" :class="riskInfo(item.level).className">{{ riskInfo(item.level).text }}</span></td>
                <td><span class="rule-code">{{ item.rule_code || '—' }}</span></td>
                <td class="risk-title">{{ item.title }}</td>
                <td class="basis-cell" :title="item.basis">{{ item.basis }}</td>
                <td>
                  <button class="doc-no" type="button" @click="router.push(`/documents/${item.doc_id}`)">
                    {{ item.doc.doc_no }}
                  </button>
                </td>
                <td class="title-text" :title="item.doc.title">{{ item.doc.title }}</td>
                <td>{{ item.doc.applicant_name }}</td>
                <td class="money">{{ formatMoney(item.doc.total_amount) }}</td>
                <td>
                  <span
                    class="badge"
                    :class="item.status === 'handled' ? 'badge-green' : item.status === 'dismissed' ? 'badge-gray' : 'badge-amber'"
                  >{{ { open: '待处理', handled: '已处理', dismissed: '已排除' }[item.status] }}</span>
                </td>
                <td>
                  <div class="confidence">
                    <span class="confidence-bar">
                      <i
                        :style="{
                          width: `${item.confidence}%`,
                          background: riskInfo(item.level).color
                        }"
                      ></i>
                    </span>
                    <span class="confidence-num">{{ item.confidence }}%</span>
                  </div>
                </td>
                <td><button class="link" type="button" @click="openRisk(item)">查看</button></td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="11">
                  <div class="empty-state">
                    <Inbox :size="30" />
                    <span>没有匹配的风险项</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.risks-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.search-box {
  width: 236px;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
}

.search-box:focus-within {
  border-color: var(--primary);
  background: #fff;
}

.search-box input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 12px;
  color: var(--text-primary);
}

.search-box input::placeholder {
  color: var(--text-muted);
}

.select-wrap {
  width: 108px;
}

.select-wrap .select {
  height: 34px;
  font-size: 12px;
}

.summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  flex: none;
}

.summary-card {
  position: relative;
  height: 84px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.summary-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.summary-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.summary-value {
  font-size: 22px;
  line-height: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.summary-label {
  font-size: 12px;
  line-height: 15px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.summary-note {
  position: absolute;
  right: 16px;
  bottom: 14px;
  font-size: 11px;
  color: var(--text-muted);
}

.list-card {
  flex: 1;
  min-width: 0;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.list-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.muted-sm {
  font-size: 12px;
  color: var(--text-muted);
}

.level-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: var(--text-secondary);
}

.level-legend span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.level-legend i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.risk-table {
  min-width: 1120px;
}

.risk-title {
  font-weight: 700;
}

.rule-code {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  padding: 2px 6px;
  background: #f2f4f7;
  border-radius: 4px;
}

.basis-cell {
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-secondary);
}

.doc-no {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
}

.doc-no:hover {
  text-decoration: underline;
}

.title-text {
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.confidence {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-bar {
  width: 58px;
  height: 5px;
  border-radius: 3px;
  background: #f2f4f7;
  overflow: hidden;
  flex: none;
}

.confidence-bar i {
  display: block;
  height: 5px;
  border-radius: 3px;
}

.confidence-num {
  font-size: 12px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.link {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 12px;
}
</style>
