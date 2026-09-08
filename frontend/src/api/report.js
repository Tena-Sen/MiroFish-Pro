import service, { requestWithRetry } from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/generate', data), 3, 1000)
}

/**
 * 检查报告状态 + 断点续传信息（R5）
 * @param {string} simulationId
 * @returns {Promise<{success, data: {has_report, report_status, report_id, interview_unlocked, completed_sections, total_sections, resumable}}>}
 */
export const checkReportStatus = (simulationId) => {
  return service.get(`/api/report/check/${simulationId}`)
}

/**
 * 获取报告生成状态
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/chat', data), 3, 1000)
}

/**
 * 下载报告 Markdown 文件（生成中下载已生成的部分章节）
 * @param {string} reportId
 * @param {string} [title] - 报告标题（用作下载文件名；不传回退 reportId）
 */
export const downloadReport = async (reportId, title) => {
  // blob 响应绕过 JSON 拦截器（Blob 无 success 字段，拦截器原样返回）
  const blob = await service.get(`/api/report/${reportId}/download`, { responseType: 'blob' })
  // 文件名用报告标题：清洗文件系统非法字符，回退 reportId
  const base = (title || '')
    .replace(/[\\/:*?"<>|\r\n\t]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[. ]+$/, '')
    .slice(0, 80)
  const filename = `${base || reportId}.md`
  const url = window.URL.createObjectURL(new Blob([blob]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
