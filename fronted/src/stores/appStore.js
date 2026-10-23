// Pinia 状态管理（Spec 8.1）：视图只与本 store 交互，数据经 api 层获取。
// mock 模式下 api 同步操作 reactive db，视图响应式更新；
// 切换真实后端后，将此处 action 改为 async 并 await api 返回值即可。
import { defineStore } from 'pinia'
import * as db from '../mock/db'
import * as api from '../api'

export const useAppStore = defineStore('app', () => {
  return {
    // 状态与查询（读）
    state: db.state,
    getDocument: db.getDocument,
    getDetails: db.getDetails,
    getAttachments: db.getAttachments,
    getRiskAnalysis: db.getRiskAnalysis,
    getRiskItems: db.getRiskItems,
    getParseResults: db.getParseResults,
    getOpinions: db.getOpinions,
    getLogs: db.getLogs,
    getTasks: db.getTasks,
    getReportByDoc: db.getReportByDoc,
    getRiskEvidences: db.getRiskEvidences,
    getApprovalQueue: db.getApprovalQueue,
    getFlowChain: db.getFlowChain,
    visibleDocuments: db.visibleDocuments,
    visibleRiskItems: db.visibleRiskItems,
    visibleLogs: db.visibleLogs,
    visibleReports: db.visibleReports,

    // 权限（Spec 5.3 矩阵）
    canViewDoc: db.canViewDoc,
    canEditDoc: db.canEditDoc,
    canWithdraw: db.canWithdraw,
    canResubmit: db.canResubmit,
    canApprove: db.canApprove,
    canConfirmComplete: db.canConfirmComplete,
    canRestore: db.canRestore,
    canHandleRisk: db.canHandleRisk,
    canRerunAnalysis: db.canRerunAnalysis,
    canExportReport: db.canExportReport,
    canViewLogs: db.canViewLogs,
    canViewApprovals: db.canViewApprovals,
    canViewAdmin: db.canViewAdmin,

    // 校验
    validateSubmitForm: db.validateSubmitForm,

    // 操作（写）
    login: api.login,
    logout: api.logout,
    createDocument: api.createDocument,
    submitDraft: api.submitDocument,
    resubmitDocument: api.resubmitDocument,
    withdrawDocument: api.withdrawDocument,
    approveDocument: api.approveTask,
    confirmComplete: api.confirmComplete,
    restoreDocument: api.restoreDocument,
    handleRiskItem: api.handleRiskItem,
    rerunAnalysis: api.rerunAnalysis,
    ensureReport: api.generateReport,
    askAi: api.askAi,
    addAttachments: db.addAttachments,
    markAllNotificationsRead: api.markNotificationsRead,
    updateRiskRule: api.updateRiskRule,
    resetDemo: db.resetDemo
  }
})
