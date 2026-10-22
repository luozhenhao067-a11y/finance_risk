<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronRight,
  Save,
  Send,
  Plus,
  Trash2,
  Upload,
  FileText,
  Image as ImageIcon,
  CircleCheck,
  CircleAlert
} from 'lucide-vue-next'
import { DOC_TYPES, EXPENSE_TYPES } from '../data/seed'
import { useAppStore } from '../stores/appStore'
import { formatMoney, fileMeta } from '../utils/format'
import { pushToast } from '../composables/useToast'

const router = useRouter()
const { state, createDocument, getFlowChain, validateSubmitForm } = useAppStore()

const form = reactive({
  doc_type: '差旅费报销',
  title: '10月上海出差差旅报销',
  dept: '市场部',
  project: '华东区渠道大会'
})

const details = ref([
  { key: 1, expense_type: '交通费', expense_date: '2026-10-15', amount: 1280, invoice_no: 'INV-88910234', remark: '上海至北京高铁' },
  { key: 2, expense_type: '住宿费', expense_date: '2026-10-16', amount: 4860, invoice_no: 'INV-88910451', remark: '北京酒店3晚' },
  { key: 3, expense_type: '餐饮费', expense_date: '2026-10-17', amount: 860.5, invoice_no: 'INV-88910987', remark: '客户接待' }
])

const attachments = ref([
  { id: 'seed-1', file_name: '高铁票.pdf', size_label: '1.2MB', mime: 'application/pdf', file_type: 'pdf' },
  { id: 'seed-2', file_name: '发票.png', size_label: '860KB', mime: 'image/png', file_type: 'image' },
  { id: 'seed-3', file_name: '行程单.jpg', size_label: '1.5MB', mime: 'image/jpeg', file_type: 'image' }
])

const fileInput = ref(null)
const saving = ref(false)
const submitting = ref(false)
let nextKey = 4

const total = computed(() =>
  details.value.reduce((acc, row) => acc + (Number(row.amount) || 0), 0)
)

const amountLabel = computed(() => {
  if (['采购付款', '合同付款'].includes(form.doc_type)) return '付款金额'
  if (form.doc_type === '借款单') return '借款金额'
  return '报销金额'
})

const completeDetails = computed(() =>
  details.value.length > 0 &&
  details.value.every((row) => row.expense_type && row.expense_date && Number(row.amount) > 0)
)

const typeOptions = computed(() => EXPENSE_TYPES[form.doc_type] || EXPENSE_TYPES['费用报销'])

const needInvoice = computed(() => ['费用报销', '差旅费报销'].includes(form.doc_type))
const needContract = computed(() => ['采购付款', '合同付款'].includes(form.doc_type))
const hasInvoiceFile = computed(() => attachments.value.some((file) => /发票|票据/i.test(file.file_name)))
const hasContractFile = computed(() => attachments.value.some((file) => /合同/i.test(file.file_name)))

const invoiceValid = computed(() => {
  if (!needInvoice.value) return true
  const pattern = /^(\d{8}|\d{10}|(INV|HT)-\d+)$/i
  return details.value.every((row) => row.invoice_no && pattern.test(String(row.invoice_no).trim()))
})

const checks = computed(() => {
  const list = [
    { label: '明细信息填写完整', ok: completeDetails.value },
    { label: `附件已上传（${attachments.value.length} 个）`, ok: attachments.value.length > 0 },
    { label: '合计金额与明细一致', ok: true }
  ]
  if (needInvoice.value) {
    list.push({ label: '发票号格式校验通过', ok: invoiceValid.value })
    list.push({ label: '至少上传 1 个发票附件', ok: hasInvoiceFile.value })
  }
  if (needContract.value) {
    list.push({ label: '已上传合同附件', ok: hasContractFile.value })
  }
  return list
})

// 审批流程（Spec 5.4：金额 ≥ ¥300,000 自动加签分管副总节点）
const flowSteps = computed(() => {
  const chain = getFlowChain({ total_amount: total.value })
  const persons = { 部门负责人审批: '李明', 分管副总审批: '赵刚', 财务审核: '王芳' }
  return chain.map((name) => ({
    name,
    person: name === '申请人提交' ? `${state.user.name} · ${form.dept}` : name === '审批完成' ? '系统归档' : persons[name],
    active: name === '申请人提交'
  }))
})

function addDetail() {
  details.value.push({
    key: nextKey++,
    expense_type: '交通费',
    expense_date: '2026-10-22',
    amount: null,
    invoice_no: '',
    remark: ''
  })
}

function removeDetail(key) {
  details.value = details.value.filter((row) => row.key !== key)
}

function openFilePicker() {
  fileInput.value?.click()
}

function onFilesSelected(event) {
  const files = Array.from(event.target.files || [])
  const accepted = []
  files.forEach((file) => {
    const meta = fileMeta(file.name, file.type)
    const allowed = ['pdf', 'png', 'jpg', 'jpeg'].includes(file.name.split('.').pop().toLowerCase())
    if (!allowed) {
      pushToast(`${file.name} 格式不支持，仅支持 PDF / PNG / JPG`, 'error')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      pushToast(`${file.name} 超过 20MB 限制`, 'error')
      return
    }
    const sizeLabel =
      file.size >= 1024 * 1024
        ? `${(file.size / 1024 / 1024).toFixed(1)}MB`
        : `${Math.max(1, Math.round(file.size / 1024))}KB`
    accepted.push({
      id: `file-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      file_name: file.name,
      size_label: sizeLabel,
      ...meta
    })
  })
  if (accepted.length) {
    attachments.value.push(...accepted)
    pushToast(`已添加 ${accepted.length} 个附件`)
  }
  event.target.value = ''
}

function validate() {
  const check = validateSubmitForm(buildPayload())
  if (!check.ok) {
    pushToast(check.message, 'error')
    return false
  }
  return true
}

function buildPayload() {
  return {
    doc_type: form.doc_type,
    title: form.title,
    dept: form.dept,
    project: form.project,
    details: details.value.map((row) => ({
      expense_type: row.expense_type,
      expense_date: row.expense_date,
      amount: Number(row.amount) || 0,
      invoice_no: row.invoice_no,
      remark: row.remark
    })),
    attachments: attachments.value.map((file) => ({
      file_name: file.file_name,
      size_label: file.size_label,
      mime: file.mime,
      file_type: file.file_type
    }))
  }
}

function saveDraft() {
  if (saving.value) return
  if (!form.title.trim()) {
    pushToast('请填写单据标题后再保存', 'error')
    return
  }
  saving.value = true
  createDocument(buildPayload(), false)
  pushToast('草稿已保存')
  router.push('/documents')
  saving.value = false
}

function submit() {
  if (submitting.value) return
  if (!validate()) return
  submitting.value = true
  const doc = createDocument(buildPayload(), true)
  pushToast('单据已提交，系统正在解析附件并进行风险分析')
  router.push(`/documents/${doc.id}`)
  submitting.value = false
}

function formatFileSize(label) {
  return label
}

const fileIcon = (file) => (file.file_type === 'image' ? ImageIcon : FileText)
</script>

<template>
  <div class="new-document">
    <header class="page-header h62">
      <div class="crumb">
        <button type="button" class="crumb-link" @click="router.push('/documents')">单据管理</button>
        <ChevronRight :size="14" class="crumb-chevron" />
        <span class="crumb-current">新建单据</span>
      </div>
      <div class="header-actions">
        <button class="btn btn-outline" type="button" :disabled="saving" @click="saveDraft">
          <Save :size="15" />
          <span>保存草稿</span>
        </button>
        <button class="btn btn-primary" type="button" :disabled="submitting" @click="submit">
          <Send :size="15" />
          <span>提交审批</span>
        </button>
      </div>
    </header>

    <div class="entry-body">
      <section class="form-card card">
        <div class="form-section">
          <h2 class="section-title">基本信息</h2>
          <div class="segmented">
            <button
              v-for="type in DOC_TYPES"
              :key="type"
              type="button"
              class="segment"
              :class="{ active: form.doc_type === type }"
              @click="form.doc_type = type"
            >
              {{ type }}
            </button>
          </div>
          <div class="form-grid">
            <div class="form-col">
              <div class="field-row">
                <label class="field-label">单据标题</label>
                <input v-model="form.title" class="input" type="text" placeholder="请输入单据标题" />
              </div>
              <div class="field-row">
                <label class="field-label">申请部门</label>
                <input v-model="form.dept" class="input" type="text" placeholder="请输入申请部门" />
              </div>
            </div>
            <div class="form-col">
              <div class="field-row">
                <label class="field-label">费用项目</label>
                <input v-model="form.project" class="input" type="text" placeholder="请输入费用归属项目" />
              </div>
              <div class="field-row">
                <label class="field-label">{{ amountLabel }}</label>
                <input
                  class="input total-input"
                  type="text"
                  readonly
                  :value="formatMoney(total, true)"
                  title="根据费用明细自动计算"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h2 class="section-title">费用明细</h2>
          <div class="detail-table">
            <div class="detail-row detail-head">
              <div class="dcell">费用类型</div>
              <div class="dcell">日期</div>
              <div class="dcell">金额</div>
              <div class="dcell">发票号</div>
              <div class="dcell">说明</div>
              <div class="dcell">操作</div>
            </div>
            <div v-for="row in details" :key="row.key" class="detail-row">
              <div class="dcell">
                <select v-model="row.expense_type" class="cell-input">
                  <option v-for="type in typeOptions" :key="type">{{ type }}</option>
                </select>
              </div>
              <div class="dcell">
                <input v-model="row.expense_date" class="cell-input" type="text" placeholder="YYYY-MM-DD" />
              </div>
              <div class="dcell amount-cell">
                <span class="amount-prefix">¥</span>
                <input v-model.number="row.amount" class="cell-input amount-input" type="number" min="0" step="0.01" />
              </div>
              <div class="dcell">
                <input v-model="row.invoice_no" class="cell-input" type="text" placeholder="发票号" />
              </div>
              <div class="dcell">
                <input v-model="row.remark" class="cell-input" type="text" placeholder="说明" />
              </div>
              <div class="dcell">
                <button class="row-delete" type="button" aria-label="删除明细" @click="removeDetail(row.key)">
                  <Trash2 :size="15" />
                </button>
              </div>
            </div>
            <button class="add-row" type="button" @click="addDetail">
              <Plus :size="15" />
              <span>添加明细</span>
            </button>
            <div class="sum-row">
              <span class="sum-label">合计金额</span>
              <span class="sum-value">{{ formatMoney(total, true) }}</span>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h2 class="section-title">附件上传</h2>
          <button class="upload-zone" type="button" @click="openFilePicker">
            <Upload :size="22" />
            <span>拖拽或点击上传附件 · 支持 PDF / PNG / JPG，单文件 ≤ 20MB</span>
          </button>
          <span v-if="needInvoice" class="attach-hint">报销类单据必须上传至少 1 个发票附件</span>
          <span v-else-if="needContract" class="attach-hint">采购付款 / 合同付款必须上传合同附件</span>
          <input
            ref="fileInput"
            class="hidden"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            multiple
            @change="onFilesSelected"
          />
          <div class="files">
            <div v-for="file in attachments" :key="file.id" class="file-card">
              <component
                :is="fileIcon(file)"
                :size="17"
                class="file-icon"
                :style="{ color: file.file_type === 'image' ? '#2563EB' : '#DC2626' }"
              />
              <div class="file-text">
                <div class="file-name">{{ file.file_name }}</div>
                <div class="file-size">{{ formatFileSize(file.size_label) }}</div>
              </div>
              <CircleCheck :size="16" class="file-ok" />
            </div>
          </div>
        </div>
      </section>

      <aside class="right-col">
        <section class="check-card card">
          <h2 class="check-title">提交前检查</h2>
          <div v-for="check in checks" :key="check.label" class="check-row" :class="{ warn: !check.ok }">
            <CircleCheck v-if="check.ok" :size="15" class="check-icon ok" />
            <CircleAlert v-else :size="15" class="check-icon warn" />
            <span>{{ check.label }}</span>
          </div>
        </section>

        <section class="flow-card card">
          <h2 class="check-title">审批流程</h2>
          <div class="steps">
            <div v-for="(step, index) in flowSteps" :key="step.name" class="step">
              <div class="step-left">
                <span class="step-dot" :class="{ active: step.active }"></span>
                <span v-if="index < flowSteps.length - 1" class="step-line"></span>
              </div>
              <div class="step-text">
                <span class="step-name" :class="{ active: step.active }">{{ step.name }}</span>
                <span class="step-person">{{ step.person }}</span>
              </div>
            </div>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.new-document {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
}

.crumb-link {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 14px;
  line-height: 17px;
  color: var(--text-secondary);
}

.crumb-link:hover {
  color: var(--primary);
}

.crumb-chevron {
  color: var(--text-secondary);
}

.crumb-current {
  font-size: 16px;
  line-height: 19px;
  font-weight: 700;
  color: var(--text-primary);
}

.entry-body {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 24px;
}

.form-card {
  flex: 1;
  min-width: 0;
  min-height: 790px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.segmented {
  display: flex;
  gap: 6px;
}

.segment {
  flex: 1;
  height: 32px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #f2f4f7;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  transition: background 0.15s ease, color 0.15s ease;
}

.segment:hover {
  background: #e9edf2;
}

.segment.active {
  background: var(--primary);
  color: #fff;
}

.form-grid {
  display: flex;
  gap: 20px;
}

.form-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.total-input {
  font-variant-numeric: tabular-nums;
}

.detail-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.detail-row {
  display: grid;
  grid-template-columns: 130px 110px 120px 140px minmax(160px, 1fr) 64px;
  align-items: center;
  min-height: 44px;
  border-bottom: 1px solid var(--border);
}

.detail-row.detail-head {
  min-height: 36px;
  background: #f9fafb;
  border-radius: 8px;
  border-bottom: none;
}

.dcell {
  padding: 0 8px;
  font-size: 13px;
  line-height: 16px;
  color: var(--text-primary);
  min-width: 0;
}

.detail-head .dcell {
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--text-secondary);
}

.cell-input {
  width: 100%;
  height: 30px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 6px;
  padding: 4px 6px;
  font-size: 13px;
  color: var(--text-primary);
  min-width: 0;
  outline: none;
}

.cell-input:hover {
  background: #f9fafb;
}

.cell-input:focus {
  background: #fff;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

select.cell-input {
  appearance: none;
  cursor: pointer;
}

.amount-cell {
  display: flex;
  align-items: center;
  gap: 1px;
}

.amount-prefix {
  font-size: 13px;
  color: var(--text-primary);
}

.amount-input {
  font-weight: 700;
  padding-left: 2px;
  font-variant-numeric: tabular-nums;
}

.amount-input::-webkit-outer-spin-button,
.amount-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.amount-input {
  -moz-appearance: textfield;
}

.row-delete {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 6px;
}

.row-delete:hover {
  color: var(--high);
  background: var(--high-bg);
}

.add-row {
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
}

.add-row:hover {
  background: var(--primary-weak);
  border-color: var(--primary-line);
}

.sum-row {
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.sum-label {
  font-size: 13px;
  line-height: 16px;
  color: var(--text-secondary);
}

.sum-value {
  font-size: 18px;
  line-height: 22px;
  font-weight: 700;
  color: var(--high);
  font-variant-numeric: tabular-nums;
}

.upload-zone {
  height: 74px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #f9fafb;
  color: var(--text-secondary);
  font-size: 13px;
}

.upload-zone:hover {
  border-color: var(--primary-line);
  background: var(--primary-weak);
  color: var(--primary);
}

.attach-hint {
  font-size: 12px;
  line-height: 15px;
  color: var(--mid);
}

.files {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.file-card {
  width: 260px;
  height: 48px;
  padding: 9px 12px;
  display: flex;
  align-items: center;
  gap: 9px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.file-icon {
  flex: none;
}

.file-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  font-size: 12px;
  line-height: 15px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 11px;
  line-height: 13px;
  color: var(--text-secondary);
}

.file-ok {
  color: var(--low);
  flex: none;
}

.right-col {
  width: 300px;
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.check-card,
.flow-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.flow-card {
  gap: 12px;
}

.check-title {
  margin: 0;
  font-size: 14px;
  line-height: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  line-height: 15px;
  color: var(--text-primary);
  white-space: nowrap;
}

.check-row.warn {
  color: var(--mid);
}

.check-icon.ok {
  color: var(--low);
}
.check-icon.warn {
  color: var(--mid);
}

.steps {
  display: flex;
  flex-direction: column;
}

.step {
  height: 48px;
  display: flex;
  gap: 10px;
}

.step-left {
  width: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.step-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #e4e7ec;
  flex: none;
}

.step-dot.active {
  background: var(--primary);
}

.step-line {
  width: 2px;
  flex: 1;
  background: #e4e7ec;
}

.step-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 1px;
}

.step-name {
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.step-name.active {
  color: var(--primary);
}

.step-person {
  font-size: 11px;
  line-height: 13px;
  color: var(--text-secondary);
}
</style>
