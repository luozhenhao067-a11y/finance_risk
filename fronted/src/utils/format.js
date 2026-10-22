export function formatMoney(value, space = false) {
  const number = Number(value) || 0
  const text = number.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
  return space ? `¥ ${text}` : `¥${text}`
}

export function formatNumber(value) {
  return (Number(value) || 0).toLocaleString('zh-CN')
}

export const riskMap = {
  high: { text: '高风险', className: 'badge-high', color: '#DC2626', bg: '#FEF2F2', line: '#FECACA' },
  mid: { text: '中风险', className: 'badge-mid', color: '#F59E0B', bg: '#FFFBEB', line: '#FDE68A' },
  low: { text: '低风险', className: 'badge-low', color: '#16A34A', bg: '#F0FDF4', line: '#BBF7D0' },
  blocking: { text: '阻断级', className: 'badge-red', color: '#DC2626', bg: '#FEF2F2', line: '#FECACA' },
  none: { text: '无风险', className: 'badge-none', color: '#667085', bg: '#F2F4F7', line: '#E4E7EC' }
}

export function riskInfo(level) {
  return riskMap[level] || riskMap.none
}

export const statusMap = {
  draft: { text: '草稿', className: 'badge-gray' },
  submitted: { text: '已提交', className: 'badge-blue' },
  analyzing: { text: '分析中', className: 'badge-amber' },
  pending_approval: { text: '审批中', className: 'badge-blue' },
  returned: { text: '已退回', className: 'badge-amber' },
  rejected: { text: '已驳回', className: 'badge-red' },
  approved: { text: '已通过', className: 'badge-green' },
  completed: { text: '已完成', className: 'badge-green' }
}

export function statusInfo(status) {
  return statusMap[status] || statusMap.draft
}

export function riskCountText(analysis) {
  if (!analysis) return '0 项风险 · 暂无分析结果'
  const total = analysis.high_count + analysis.mid_count + analysis.low_count
  return `${total} 项风险 · 最高等级取${riskInfo(analysis.overall_level).text}`
}

export function fileMeta(name, mime = '') {
  const ext = name.split('.').pop().toLowerCase()
  if (ext === 'pdf') return { file_type: 'pdf', mime: 'application/pdf' }
  if (['png', 'jpg', 'jpeg'].includes(ext)) {
    return { file_type: 'image', mime: mime || (ext === 'png' ? 'image/png' : 'image/jpeg') }
  }
  return { file_type: 'pdf', mime }
}
