<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Users, Building2, ShieldCheck, Inbox } from 'lucide-vue-next'
import { useAppStore } from '../stores/appStore'
import { riskInfo } from '../utils/format'
import { pushToast } from '../composables/useToast'
import { syncRules } from '../api/realSync'

const router = useRouter()
const store = useAppStore()
const { canViewAdmin, updateRiskRule } = store

// 权限（Spec 4.10）：仅系统管理员可见
if (!canViewAdmin()) {
  router.replace('/dashboard')
}

onMounted(() => {
  syncRules()
})

const keyword = ref('')

const users = computed(() => store.state.users)
const depts = computed(() => store.state.depts)
const rules = computed(() => store.state.riskRules)

const filteredUsers = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return users.value
  return users.value.filter((user) =>
    [user.name, user.role, user.dept].some((value) => String(value || '').toLowerCase().includes(text))
  )
})

const roles = computed(() => {
  const order = ['APPLICANT', 'DEPT_MANAGER', 'FINANCE', 'ADMIN']
  const roleUsers = users.value.filter((user) => user.role_code === store.state.user?.role_code)
  return order.map((code) => {
    const all = users.value.filter((user) => user.role_code === code)
    return {
      code,
      name: all[0]?.role || code,
      count: all.length,
      current: roleUsers.length && roleUsers[0].role_code === code
    }
  })
})

const enabledCount = computed(() => rules.value.filter((rule) => rule.enabled).length)

function toggleRule(rule) {
  updateRiskRule(rule.code, { enabled: !rule.enabled })
  pushToast(`风险规则 ${rule.code} 已${rule.enabled ? '启用' : '停用'}`)
}
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div class="header-title-box">
        <h1 class="header-title">系统管理</h1>
        <div class="header-subtitle">用户与部门维护 · 风险规则引擎配置 · 仅系统管理员可见</div>
      </div>
    </header>

    <div class="page-body">
      <section class="card block">
        <div class="block-head">
          <div class="block-title">
            <div class="title-icon"><Users :size="17" /></div>
            <div>
              <h2 class="section-title">用户与角色</h2>
              <span class="muted-sm">共 {{ users.length }} 个演示账号 · 4 种角色</span>
            </div>
          </div>
          <div class="search-box">
            <input v-model="keyword" type="text" placeholder="搜索姓名 / 角色 / 部门" />
          </div>
        </div>

        <div class="role-row">
          <div v-for="role in roles" :key="role.code" class="role-chip" :class="{ current: role.current }">
            <span class="role-code">{{ role.code }}</span>
            <span class="role-name">{{ role.name }}</span>
            <span class="role-count">{{ role.count }} 人</span>
          </div>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 110px">姓名</th>
                <th style="width: 150px">角色</th>
                <th style="width: 130px">所属部门</th>
                <th style="width: 170px">角色编码</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredUsers" :key="user.id">
                <td class="user-cell">
                  <span class="avatar">{{ user.avatar }}</span>
                  <span>{{ user.name }}</span>
                </td>
                <td>{{ user.role }}</td>
                <td>{{ user.dept }}</td>
                <td><span class="code-text">{{ user.role_code }}</span></td>
              </tr>
              <tr v-if="!filteredUsers.length">
                <td colspan="4">
                  <div class="empty-state">
                    <Inbox :size="30" />
                    <span>没有匹配的用户</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card block">
        <div class="block-head">
          <div class="block-title">
            <div class="title-icon"><Building2 :size="17" /></div>
            <div>
              <h2 class="section-title">部门</h2>
              <span class="muted-sm">共 {{ depts.length }} 个部门</span>
            </div>
          </div>
        </div>
        <div class="dept-row">
          <div v-for="dept in depts" :key="dept.id" class="dept-chip">
            {{ dept.name }}
            <span class="dept-count">{{ users.filter((user) => user.dept_id === dept.id).length }} 人</span>
          </div>
        </div>
      </section>

      <section class="card block">
        <div class="block-head">
          <div class="block-title">
            <div class="title-icon"><ShieldCheck :size="17" /></div>
            <div>
              <h2 class="section-title">风险规则配置</h2>
              <span class="muted-sm">共 {{ rules.length }} 条规则 · 已启用 {{ enabledCount }} 条 · 停用后分析引擎不再命中该规则</span>
            </div>
          </div>
        </div>

        <div class="table-wrap">
          <table class="data-table rules-table">
            <thead>
              <tr>
                <th style="width: 76px">规则编码</th>
                <th style="width: 150px">规则名称</th>
                <th style="width: 92px">风险等级</th>
                <th style="width: 190px">适用单据</th>
                <th style="min-width: 220px">规则参数</th>
                <th style="width: 90px">状态</th>
                <th style="width: 84px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in rules" :key="rule.code" :class="{ disabled: !rule.enabled }">
                <td><span class="code-text">{{ rule.code }}</span></td>
                <td class="rule-name">{{ rule.name }}</td>
                <td><span class="badge" :class="riskInfo(rule.level).className">{{ riskInfo(rule.level).text }}</span></td>
                <td>{{ rule.docTypes }}</td>
                <td class="params-cell" :title="rule.params">{{ rule.params }}</td>
                <td>
                  <span class="badge" :class="rule.enabled ? 'badge-green' : 'badge-gray'">
                    {{ rule.enabled ? '已启用' : '已停用' }}
                  </span>
                </td>
                <td>
                  <button class="btn btn-xs" :class="rule.enabled ? 'btn-outline' : 'btn-soft'" type="button" @click="toggleRule(rule)">
                    {{ rule.enabled ? '停用' : '启用' }}
                  </button>
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
.admin-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.page-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.block {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.block-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--primary-weak);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.muted-sm {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.search-box {
  width: 220px;
  height: 34px;
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
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

.role-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.role-chip {
  min-width: 190px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.role-chip.current {
  border-color: var(--primary);
  background: var(--primary-weak);
}

.role-code {
  font-size: 11px;
  line-height: 13px;
  font-weight: 700;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
}

.role-name {
  flex: 1;
  font-size: 13px;
  line-height: 16px;
  font-weight: 700;
}

.role-count {
  font-size: 11px;
  line-height: 13px;
  color: var(--text-secondary);
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary-weak);
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.code-text {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.dept-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.dept-chip {
  min-width: 140px;
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
}

.dept-count {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-secondary);
}

.rules-table {
  min-width: 900px;
}

tr.disabled td {
  color: var(--text-muted);
}

tr.disabled .code-text,
tr.disabled .rule-name {
  color: var(--text-muted);
}

.rule-name {
  font-weight: 700;
}

.params-cell {
  max-width: 240px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-xs {
  height: 26px;
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 6px;
}
</style>
