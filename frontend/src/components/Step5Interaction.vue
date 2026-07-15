<template>
  <div class="interaction-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report Style -->
      <div class="left-panel report-style" ref="leftPanel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <div class="report-header-block">
            <div class="report-meta">
              <span class="report-tag">Prediction Report</span>
              <span class="report-id">ID: {{ reportId || 'REF-2024-X92' }}</span>
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <div class="header-divider"></div>
          </div>

          <!-- Sections List -->
          <div class="sections-list">
            <div 
              v-for="(section, idx) in reportOutline.sections" 
              :key="idx"
              class="report-section-item"
              :class="{ 
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <div class="section-header-row" @click="toggleSectionCollapse(idx)" :class="{ 'clickable': isSectionCompleted(idx + 1) }">
                <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
                <h3 class="section-title">{{ section.title }}</h3>
                <svg 
                  v-if="isSectionCompleted(idx + 1)" 
                  class="collapse-icon" 
                  :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                  viewBox="0 0 24 24" 
                  width="20" 
                  height="20" 
                  fill="none" 
                  stroke="currentColor" 
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
              
              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>
                
                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" stroke-width="4" stroke="#E5E7EB"></circle>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke="#4B5563" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">{{ $t('step4.generatingSection', { title: section.title }) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Waiting State -->
        <div v-if="!reportOutline" class="waiting-placeholder">
          <div class="waiting-animation">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">Waiting for Report Agent...</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Interaction Interface -->
      <div class="right-panel" ref="rightPanel">
        <!-- 返回按钮 -->
        <button class="back-step-btn-interaction" @click="goBack">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          <span>{{ $t('common.back') }} to Step 4</span>
        </button>

        <!-- Unified Action Bar - Professional Design -->
        <div class="action-bar">
        <div class="action-bar-header">
          <svg class="action-bar-icon" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <div class="action-bar-text">
            <span class="action-bar-title">{{ $t('step5.interactiveTools') }}</span>
            <span class="action-bar-subtitle mono">{{ $t('step5.agentsAvailable', { count: profiles.length }) }}</span>
          </div>
        </div>
          <div class="action-bar-tabs">
            <button 
              class="tab-pill"
              :class="{ active: activeTab === 'chat' && chatTarget === 'report_agent' }"
              @click="selectReportAgentChat"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
              </svg>
              <span>{{ $t('step5.chatWithReportAgent') }}</span>
            </button>
            <div class="agent-dropdown" v-if="profiles.length > 0">
              <button 
                class="tab-pill agent-pill"
                :class="{ active: activeTab === 'chat' && chatTarget === 'agent' }"
                @click="toggleAgentDropdown"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span>{{ selectedAgent ? selectedAgent.username : $t('step5.chatWithAgent') }}</span>
                <svg class="dropdown-arrow" :class="{ open: showAgentDropdown }" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
              <div v-if="showAgentDropdown" class="dropdown-menu">
                <div class="dropdown-header">{{ $t('step5.selectChatTarget') }}</div>
                <div 
                  v-for="(agent, idx) in profiles" 
                  :key="idx"
                  class="dropdown-item"
                  @click="selectAgent(agent, idx)"
                >
                  <div class="agent-avatar">{{ (agent.username || 'A')[0] }}</div>
                  <div class="agent-info">
                    <span class="agent-name">{{ agent.username }}</span>
                    <span class="agent-role">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="tab-divider"></div>
            <button
              class="tab-pill survey-pill"
              :class="{ active: activeTab === 'survey' }"
              @click="selectSurveyTab"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>{{ $t('step5.sendSurvey') }}</span>
            </button>
          </div>
        </div>

        <!-- Environment Status Indicator — 必修 11：提到顶层，对话/采访两个 tab 都可见 -->
        <!-- 之前放在 chat + report_agent 嵌套里，survey 模式完全看不到 env 状态 -->
        <!-- 用户采访失败 504 时不知道去哪重启 → 把 env 状态提到 tab 切换区下方 -->
        <div v-if="props.simulationId" class="env-status-bar" :class="envStatus || 'unknown'">
          <span v-if="envStatusLoading" class="env-status-dot env-loading">⋯</span>
          <span v-else-if="envStatus === 'alive'" class="env-status-dot env-alive">●</span>
          <span v-else-if="envStatus === 'stopped'" class="env-status-dot env-stopped">●</span>
          <span v-else class="env-status-dot env-unknown">●</span>
          <span class="env-status-text">
            <template v-if="envStatusLoading">{{ $t('step5.checkingEnv') }}</template>
            <template v-else-if="isRestarting">{{ $t(stageInfo.key, stageInfo.params) }}</template>
            <template v-else-if="envStatus === 'alive'">{{ $t('step5.envAlive') }}</template>
            <template v-else-if="envStatus === 'stopped'">{{ $t('step5.envStopped') }}</template>
            <template v-else>{{ $t('step5.envUnknown') }}</template>
          </span>
          <!-- 一键恢复入口（智能判断：1+ 快照展示选择器，否则 force 重启） -->
          <!-- 修复：v-if 改 v-show，避免 picker 展示或重启进行中按钮整段消失 -->
          <button
            v-show="envStatus === 'stopped' && !envStatusLoading && !showSnapshotPicker && !isRestarting"
            class="env-status-action"
            :disabled="isRestarting"
            @click="handleEnvStoppedAction"
            :title="$t('step5.envStoppedHint')"
          >
            <span v-if="isRestarting">{{ $t('step5.envRestarting') }}</span>
            <span v-else-if="restartMode === 'restore'">{{ $t('step5.restoring') }}</span>
            <span v-else-if="restartMode === 'fresh'">{{ $t('step5.freshStarting') }}</span>
            <span v-else>{{ $t('step5.envStoppedAction') }}</span>
          </button>
          <!-- 强制从头启动按钮 —— 永跳过 picker,清空并从 R0 重新开始 -->
          <!-- 视觉上稍弱一点,避免和主入口抢镜;鼠标 hover 显示提示"已有数据会被清空" -->
          <button
            v-show="envStatus === 'stopped' && !envStatusLoading && !isRestarting"
            class="env-status-action env-status-action-force"
            :disabled="isRestarting"
            @click="handleForceFreshStart"
            :title="$t('step5.envForceFreshHint')"
          >
            {{ $t('step5.envForceFreshBtn') }}
          </button>
          <!-- 恢复期进度由独立的大 banner 接管 (.restart-progress-area),这里不再放小转圈避免双转圈 -->
        </div>

        <!-- 重启成功短暂 banner —— 让用户明确知道"已启动" -->
        <Transition name="restart-success">
          <div v-if="showRestartSuccess" class="restart-success-banner">
            <span class="restart-success-icon">✓</span>
            <span class="restart-success-text">{{ $t('step5.envRestartSuccessBanner') }}</span>
          </div>
        </Transition>

        <!-- 恢复期进度区：picker 与大型 progress banner 互斥 -->
        <!-- 设计意图:让用户在 picker 中点击后立刻看到大型 banner,绝不可能错过进度反馈 -->
        <div v-if="props.simulationId && isRestarting" class="restart-progress-area">
          <!-- picking 阶段显示 picker -->
          <div v-if="showSnapshotPicker && availableSnapshots.length > 0" class="snapshot-picker">
            <div class="snapshot-picker-title">{{ $t('step5.snapshotPickerTitle') }}</div>
            <div class="snapshot-picker-hint">{{ $t('step5.snapshotPickerHint') }}</div>
            <!-- 自动倒计时:5s 不选 → 自动 force fresh start,减少点击次数 -->
            <div class="snapshot-picker-countdown">
              <span class="countdown-dot"></span>
              {{ $t('step5.snapshotPickerCountdown', { seconds: pickerCountdown }) }}
              <button type="button" class="countdown-skip" @click="chooseFreshStart">
                {{ $t('step5.snapshotPickerCountdownSkip') }}
              </button>
            </div>
            <div class="snapshot-picker-list">
              <div
                v-for="snap in availableSnapshots"
                :key="snap.snapshot_name"
                class="snapshot-picker-item"
                @click="chooseSnapshot(snap)"
              >
                <div class="snapshot-picker-item-name">{{ snap.snapshot_name }}</div>
                <div class="snapshot-picker-item-meta">
                  <span v-if="(snap.current_round ?? snap.run_state?.current_round) !== undefined">
                    R{{ snap.current_round ?? snap.run_state?.current_round }}
                  </span>
                  <span v-if="snap.created_at">{{ snap.created_at.split('T')[0] }} {{ snap.created_at.split('T')[1]?.substring(0, 5) }}</span>
                </div>
              </div>
            </div>
            <div class="snapshot-picker-actions">
              <button
                class="snapshot-picker-btn fresh"
                @click="chooseFreshStart"
              >
                {{ $t('step5.snapshotPickerFresh') }}
              </button>
              <button
                class="snapshot-picker-btn cancel"
                @click="cancelPickSnapshot"
              >
                {{ $t('common.cancel') }}
              </button>
            </div>
          </div>

          <!-- 其他阶段显示大型进度 banner,用户绝对不可能错过 -->
          <div
            v-else
            class="restart-progress-banner"
            :class="'stage-' + recoveryStage"
          >
            <div class="restart-progress-spinner" aria-hidden="true"></div>
            <div class="restart-progress-content">
              <div class="restart-progress-stage">{{ $t(stageInfo.key, stageInfo.params) }}</div>
              <div class="restart-progress-hint">
                {{
                  recoveryStage === 'listing' ? '正在加载快照列表…' :
                  recoveryStage === 'restoring' ? '正在恢复世界状态(恢复后启动会接着跑)…' :
                  recoveryStage === 'starting' ? '正在拉起模拟子进程(通常 5–30 秒,请勿关闭页面)…' :
                  recoveryStage === 'waiting_alive' ? '等待环境上线,请勿重复点击…' :
                  '正在准备,请稍候…'
                }}
              </div>
            </div>
          </div>
        </div>

        <!-- Chat Mode -->
        <div v-if="activeTab === 'chat'" class="chat-container">

          <!-- Report Agent Tools Card -->
          <div v-if="chatTarget === 'report_agent'" class="report-agent-tools-card">
            <div class="tools-card-header">
              <div class="tools-card-avatar">R</div>
              <div class="tools-card-info">
                <div class="tools-card-name">{{ $t('step5.reportAgentChat') }}</div>
                <div class="tools-card-subtitle">{{ $t('step5.reportAgentDesc') }}</div>
              </div>
              <button class="tools-card-toggle" @click="showToolsDetail = !showToolsDetail">
                <svg :class="{ 'is-expanded': showToolsDetail }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>

            <!-- Environment Status Indicator — 必修 11：已移到 tab 切换区下方，对两个 tab 都可见 -->
            <div v-if="showToolsDetail" class="tools-card-body">
              <div class="tools-grid">
                <div class="tool-item tool-purple">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolInsightForge') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolInsightForgeDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-blue">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolPanoramaSearch') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolPanoramaSearchDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-orange">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolQuickSearch') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolQuickSearchDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-green">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolInterviewSubAgent') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolInterviewSubAgentDesc') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Agent Profile Card -->
          <div v-if="chatTarget === 'agent' && selectedAgent" class="agent-profile-card">
            <div class="profile-card-header">
              <div class="profile-card-avatar">{{ (selectedAgent.username || 'A')[0] }}</div>
              <div class="profile-card-info">
                <div class="profile-card-name">{{ selectedAgent.username }}</div>
                <div class="profile-card-meta">
                  <span v-if="selectedAgent.name" class="profile-card-handle">@{{ selectedAgent.name }}</span>
                  <span class="profile-card-profession">{{ selectedAgent.profession || $t('step2.unknownProfession') }}</span>
                </div>
              </div>
              <button class="profile-card-toggle" @click="showFullProfile = !showFullProfile">
                <svg :class="{ 'is-expanded': showFullProfile }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showFullProfile && selectedAgent.bio" class="profile-card-body">
              <div class="profile-card-bio">
                <div class="profile-card-label">{{ $t('step5.profileBio') }}</div>
                <p>{{ selectedAgent.bio }}</p>
              </div>
            </div>
          </div>

          <!-- Chat Messages -->
          <div class="chat-messages" ref="chatMessages">
            <div v-if="chatHistory.length === 0" class="chat-empty">
              <div class="empty-icon">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </div>
              <p class="empty-text">
                {{ chatTarget === 'report_agent' ? $t('step5.chatEmptyReportAgent') : $t('step5.chatEmptyAgent') }}
              </p>
            </div>
            <div 
              v-for="(msg, idx) in chatHistory" 
              :key="idx"
              class="chat-message"
              :class="msg.role"
            >
              <div class="message-avatar">
                <span v-if="msg.role === 'user'">U</span>
                <span v-else>{{ msg.role === 'assistant' && chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="message-header">
                  <span class="sender-name">
                    {{ msg.role === 'user' ? 'You' : (chatTarget === 'report_agent' ? 'Report Agent' : (selectedAgent?.username || 'Agent')) }}
                  </span>
                  <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                </div>
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
            <div v-if="isSending" class="chat-message assistant">
              <div class="message-avatar">
                <span>{{ chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Chat Input -->
          <div class="chat-input-area">
            <!-- 模拟世界停止时,在输入框上方显眼的内嵌横幅 -->
            <div v-if="envStatus === 'stopped' && !envStatusLoading" class="chat-stopped-banner">
              <span class="chat-stopped-icon">⚠</span>
              <span class="chat-stopped-text">{{ $t('step5.envStoppedInlineHint') }}</span>
              <button
                type="button"
                class="chat-stopped-btn"
                :disabled="isRestarting"
                @click="handleEnvStoppedAction"
              >
                <span v-if="isRestarting" class="loading-spinner-small"></span>
                {{ isRestarting ? $t('step5.envRestarting') : $t('step5.envStoppedAction') }}
              </button>
              <button
                type="button"
                class="chat-stopped-btn chat-stopped-btn-secondary"
                :disabled="isRestarting"
                @click="handleChatOnlyStart"
              >
                {{ $t('step5.envStoppedChatOnlyBtn') }}
              </button>
            </div>
            <div class="chat-input-row">
              <textarea
                v-model="chatInput"
                class="chat-input"
                :placeholder="envStatus === 'stopped' ? $t('step5.chatInputPlaceholderStopped') : $t('step5.chatInputPlaceholder')"
                @keydown.enter.exact.prevent="sendMessage"
                :disabled="isSending || (!selectedAgent && chatTarget === 'agent') || envStatus === 'stopped'"
                rows="1"
                ref="chatInputRef"
              ></textarea>
              <!-- 平台选择器: "都问 / 只问 Reddit / 只问 Twitter",默认 both 保留现有行为 -->
              <div class="platform-selector" role="radiogroup" :aria-label="t('step5.platformLabel')">
                <button
                  type="button"
                  class="platform-pill"
                  :class="{ active: selectedPlatform === 'both' }"
                  :aria-pressed="selectedPlatform === 'both'"
                  :disabled="envStatus === 'stopped' && !envStatusLoading"
                  @click="selectedPlatform = 'both'"
                >
                  {{ t('step5.platformBoth') }}
                </button>
                <button
                  type="button"
                  class="platform-pill"
                  :class="{ active: selectedPlatform === 'reddit' }"
                  :aria-pressed="selectedPlatform === 'reddit'"
                  :disabled="envStatus === 'stopped' && !envStatusLoading"
                  @click="selectedPlatform = 'reddit'"
                >
                  {{ t('step5.platformReddit') }}
                </button>
                <button
                  type="button"
                  class="platform-pill"
                  :class="{ active: selectedPlatform === 'twitter' }"
                  :aria-pressed="selectedPlatform === 'twitter'"
                  :disabled="envStatus === 'stopped' && !envStatusLoading"
                  @click="selectedPlatform = 'twitter'"
                >
                  {{ t('step5.platformTwitter') }}
                </button>
              </div>
              <button
                class="send-btn"
                @click="sendMessage"
                :disabled="!chatInput.trim() || isSending || (!selectedAgent && chatTarget === 'agent') || envStatus === 'stopped'"
              >
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Survey Mode -->
        <div v-if="activeTab === 'survey'" class="survey-container">
          <!-- Survey Setup -->
          <div class="survey-setup">
            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $t('step5.selectSurveyTarget') }}</span>
                <span class="selection-count">{{ $t('step5.selectedCount', { selected: selectedAgents.size, total: profiles.length }) }}</span>
              </div>
              <div class="agents-grid">
                <label 
                  v-for="(agent, idx) in profiles" 
                  :key="idx"
                  class="agent-checkbox"
                  :class="{ checked: selectedAgents.has(idx) }"
                >
                  <input 
                    type="checkbox" 
                    :checked="selectedAgents.has(idx)"
                    @change="toggleAgentSelection(idx)"
                  >
                  <div class="checkbox-avatar">{{ (agent.username || 'A')[0] }}</div>
                  <div class="checkbox-info">
                    <span class="checkbox-name">{{ agent.username }}</span>
                    <span class="checkbox-role">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                  <div class="checkbox-indicator">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                </label>
              </div>
              <div class="selection-actions">
                <button class="action-link" @click="selectAllAgents">{{ $t('step5.selectAll') }}</button>
                <span class="action-divider">|</span>
                <button class="action-link" @click="clearAgentSelection">{{ $t('step5.clearSelection') }}</button>
              </div>
            </div>

            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $t('step5.surveyQuestions') }}</span>
              </div>
              <textarea 
                v-model="surveyQuestion"
                class="survey-input"
                :placeholder="$t('step5.surveyInputPlaceholder')"
                rows="3"
              ></textarea>
            </div>

            <!-- 模拟停止时 survey 顶部也加 banner -->
            <div v-if="envStatus === 'stopped' && !envStatusLoading" class="chat-stopped-banner">
              <span class="chat-stopped-icon">⚠</span>
              <span class="chat-stopped-text">{{ $t('step5.envStoppedInlineHint') }}</span>
              <button
                type="button"
                class="chat-stopped-btn"
                :disabled="isRestarting"
                @click="handleEnvStoppedAction"
              >
                <span v-if="isRestarting" class="loading-spinner-small"></span>
                {{ isRestarting ? $t('step5.envRestarting') : $t('step5.envStoppedAction') }}
              </button>
              <button
                type="button"
                class="chat-stopped-btn chat-stopped-btn-secondary"
                :disabled="isRestarting"
                @click="handleChatOnlyStart"
              >
                {{ $t('step5.envStoppedChatOnlyBtn') }}
              </button>
            </div>

            <!-- 平台选择器:与 chat 共用 selectedPlatform,语义一致 -->
            <div class="platform-selector platform-selector-survey" role="radiogroup" :aria-label="t('step5.platformLabel')">
              <button
                type="button"
                class="platform-pill"
                :class="{ active: selectedPlatform === 'both' }"
                :aria-pressed="selectedPlatform === 'both'"
                :disabled="envStatus === 'stopped' && !envStatusLoading"
                @click="selectedPlatform = 'both'"
              >
                {{ t('step5.platformBoth') }}
              </button>
              <button
                type="button"
                class="platform-pill"
                :class="{ active: selectedPlatform === 'reddit' }"
                :aria-pressed="selectedPlatform === 'reddit'"
                :disabled="envStatus === 'stopped' && !envStatusLoading"
                @click="selectedPlatform = 'reddit'"
              >
                {{ t('step5.platformReddit') }}
              </button>
              <button
                type="button"
                class="platform-pill"
                :class="{ active: selectedPlatform === 'twitter' }"
                :aria-pressed="selectedPlatform === 'twitter'"
                :disabled="envStatus === 'stopped' && !envStatusLoading"
                @click="selectedPlatform = 'twitter'"
              >
                {{ t('step5.platformTwitter') }}
              </button>
            </div>

            <button
              class="survey-submit-btn"
              :disabled="selectedAgents.size === 0 || !surveyQuestion.trim() || isSurveying || envStatus === 'stopped'"
              @click="submitSurvey"
            >
              <span v-if="isSurveying" class="loading-spinner"></span>
              <span v-else>{{ $t('step5.submitSurvey') }}</span>
            </button>
          </div>

          <!-- Survey Results -->
          <div v-if="surveyResults.length > 0" class="survey-results">
            <div class="results-header">
              <span class="results-title">{{ $t('step5.surveyResults') }}</span>
              <span class="results-count">{{ $t('step5.surveyResultsCount', { count: surveyResults.length }) }}</span>
            </div>
            <div class="results-list">
              <div 
                v-for="(result, idx) in surveyResults" 
                :key="idx"
                class="result-card"
              >
                <div class="result-header">
                  <div class="result-avatar">{{ (result.agent_name || 'A')[0] }}</div>
                  <div class="result-info">
                    <span class="result-name">{{ result.agent_name }}</span>
                    <span class="result-role">{{ result.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                </div>
                <div class="result-question">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  <span>{{ result.question }}</span>
                </div>
                <div class="result-answer" v-html="renderMarkdown(result.answer)"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { chatWithReport, getReport, getAgentLog } from '../api/report'
import { interviewAgents, getSimulationProfilesRealtime, getEnvStatus, startSimulation, listSnapshots, restoreSnapshot } from '../api/simulation'

const { t } = useI18n()

// 环境状态
const envStatus = ref(null) // 'alive' | 'stopped' | null (unknown)
const envStatusLoading = ref(false)

const refreshEnvStatus = async () => {
  if (!props.simulationId) return
  envStatusLoading.value = true
  try {
    const res = await getEnvStatus({ simulation_id: props.simulationId })
    if (res.success && res.data) {
      envStatus.value = res.data.env_alive ? 'alive' : 'stopped'
    }
  } catch (err) {
    console.warn('检查环境状态失败:', err)
  } finally {
    envStatusLoading.value = false
  }
}

// 优化 S5：env 关闭时的智能恢复入口
// 用户期望：恢复之前的模拟世界状态（不是 force 重启）
// 策略：
//   1. 检测所有 final_/fail_ 快照
//   2. 只有 1 个 → 自动用它恢复
//   3. 有 ≥2 个 → 让用户选（按 current_round 倒序）
//   4. 没有快照 → fallback 到 force=true 全新启动
// 修复 UX：选完快照后立即关闭 picker，防止用户以为无反应而反复点击
// 同时把整条链路拆成可观察的阶段（listing / picking / restoring / starting / waiting_alive），
// 在 env-status-bar 显示 spinner + 阶段文案，让前端始终有可见反馈
const isRestarting = ref(false)
const restartMode = ref(null) // 'restore' | 'fresh' | null
const showSnapshotPicker = ref(false)  // 多快照选择器展开状态
const availableSnapshots = ref([])  // 可恢复的快照列表
const pickerCountdown = ref(5)         // 倒计时:5s 不选 → 自动 force fresh start
let pickerCountdownTimer = null       // 倒计时句柄
// 恢复阶段：'idle' | 'listing' | 'picking' | 'restoring' | 'starting' | 'waiting_alive'
// 用于 env-status-bar 显示阶段文案 + 进度 banner
const recoveryStage = ref('idle')

// 状态机式 picker：pickedSnapshot 由用户点击设置，由 watch 触发下游异步流程
// 取代之前 Promise-based picker —— 避免 promise race / 用户看不见的状态变化
const pickedSnapshot = ref(null)        // 当前正在恢复的快照（或 '__FRESH__' 或 null）
const pendingSnapshotsForPicker = ref([])  // 暂存 listSnapshots 返回值，给 watch 选
// 当前正在恢复的快照名（给文案模板 {name} 用的）
const restoringSnapshotName = ref('')

// stageInfo:把 recoveryStage 映射到 i18n key + params,模板用 stageInfo.key, stageInfo.params 渲染
// 修复 "() 空括号" bug:restoring 阶段带 name 参数,其他阶段不带 params
const stageInfo = computed(() => {
  switch (recoveryStage.value) {
    case 'listing':       return { key: 'step5.envStageListing', params: {} }
    case 'picking':       return { key: 'step5.envStagePicking', params: {} }
    case 'restoring':     return { key: 'step5.envRestoreTriggered', params: { name: restoringSnapshotName.value } }
    case 'starting':      return { key: 'step5.envRestartTriggered', params: {} }
    case 'waiting_alive': return { key: 'step5.envStageWaitingAlive', params: {} }
    default:              return { key: 'step5.envRestarting', params: {} }
  }
})

// 倒计时逻辑:picker 弹出后 5s 不选 → 自动 force fresh start
// 用户报"每次要点 2 次",这是减少点击次数的最直接办法
const stopPickerCountdown = () => {
  if (pickerCountdownTimer) {
    clearInterval(pickerCountdownTimer)
    pickerCountdownTimer = null
  }
}

watch(showSnapshotPicker, (isShown) => {
  if (isShown) {
    pickerCountdown.value = 5
    stopPickerCountdown()
    pickerCountdownTimer = setInterval(() => {
      pickerCountdown.value -= 1
      if (pickerCountdown.value <= 0) {
        stopPickerCountdown()
        // 自动走 fresh start 流程
        chooseFreshStart()
      }
    }, 1000)
  } else {
    stopPickerCountdown()
    pickerCountdown.value = 5  // 重置,下次显示时重新倒计时
  }
})

// 重启成功后短暂显示绿色 banner,给用户明确"已启动"反馈
const showRestartSuccess = ref(false)
let successTimer = null
const flashRestartSuccess = () => {
  showRestartSuccess.value = true
  if (successTimer) clearTimeout(successTimer)
  successTimer = setTimeout(() => {
    showRestartSuccess.value = false
  }, 4000)
}

// step5 的辅助:从 snapshot 对象里提取当前轮次
const getSnapshotRound = (snap) => {
  if (!snap) return 0
  return snap.current_round ?? snap.run_state?.current_round ?? 0
}

// 强制从头启动 —— 跳过快照 picker,直接 force=true 全新启动
// 跟 "一键重启" 不同:这个按钮永不弹 picker,适合用户明确想清空重来的场景
const handleForceFreshStart = async () => {
  if (!props.simulationId || isRestarting.value) return
  isRestarting.value = true
  pickedSnapshot.value = null
  recoveryStage.value = 'starting'
  addLog(t('step5.envForceFreshTriggered'))
  try {
    // 从头开始 = force 清空 + 从 R3 开始(跳过 R0/R1/R2)
    // 后端跑模拟循环时不会立刻写 env_status.json=alive(要等 144 轮跑完),
    // 所以不等 polling,API 200 就立刻跳 Step 3 监控
    const res = await startSimulation({
      simulation_id: props.simulationId,
      platform: 'parallel',
      force: true,
      start_round: 3,  // 跳过 R0/R1/R2
      enable_graph_memory_update: true
    })
    if (res.success) {
      addLog(t('step5.envForceFreshNavigating'))
      resetRestartState()  // 复位 isRestarting,免得组件卸载后状态残留
      goBack('env_stopped')  // 立刻跳 Step 3
    } else {
      addLog(t('step5.envRestartFailed', { error: res.error || '' }))
      resetRestartState()
    }
  } catch (err) {
    addLog(t('step5.envRestartException', { error: err.message }))
    resetRestartState()
  }
}

const handleEnvStoppedAction = async () => {
  if (!props.simulationId || isRestarting.value) return
  isRestarting.value = true
  recoveryStage.value = 'listing'
  pickedSnapshot.value = null
  addLog(t('step5.envStoppedActionHint'))
  try {
    // Step 1：检测所有 final_/fail_ 快照
    const snapRes = await listSnapshots(props.simulationId)
    const allSnapshots = snapRes?.data?.snapshots || []
    // 过滤有意义的快照，按轮次从高到低排序
    const meaningful = allSnapshots
      .filter(s => s.snapshot_name && (
        s.snapshot_name.startsWith('final_') ||
        s.snapshot_name.startsWith('fail_')
      ))
      .sort((a, b) => {
        // 优先按 current_round 倒序；同轮次按 created_at 倒序
        const ra = a.run_state?.current_round || 0
        const rb = b.run_state?.current_round || 0
        if (rb !== ra) return rb - ra
        return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
      })

    availableSnapshots.value = meaningful
    pendingSnapshotsForPicker.value = meaningful

    // Step 2：决定恢复路径
    if (meaningful.length === 0) {
      // 0 个快照 → force 全新启动（不进入 picker）
      recoveryStage.value = 'starting'
      // 直接走 freshStart 流程
      await doFreshStart()
      return
    }

    // 1 个或多个快照 → 等待用户 picker 交互
    // watcher(pickedSnapshot) 会接管后续：选了快照 → restore + start；选了 __FRESH__ → freshStart
    recoveryStage.value = 'picking'
    showSnapshotPicker.value = true
    // 此处不阻塞。后台 watch 监控 pickedSnapshot 变化触发异步恢复
  } catch (err) {
    addLog(t('step5.envRestartException', { error: err.message }))
    // 异常分支兜底复位
    isRestarting.value = false
    restartMode.value = null
    recoveryStage.value = 'idle'
    showSnapshotPicker.value = false
    availableSnapshots.value = []
  }
}

// 用户点 "Chat-Only" 按钮：跳过 rounds 直接进 IPC wait,只适合只想 chat 不想要完整 simulation 的场景。
// 不走 snapshot picker,直接走 freshStart 路径(后端翻译成 start_round=total_rounds)。
const handleChatOnlyStart = async () => {
  if (!props.simulationId || isRestarting.value) return
  isRestarting.value = true
  addLog(t('step5.envStoppedChatOnlyHint'))
  try {
    const ok = await doFreshStart({ chatOnly: true })
    if (!ok) {
      addLog(t('step5.envStoppedChatOnlyFailed'))
    }
  } catch (err) {
    addLog(t('step5.envStoppedChatOnlyFailed', { error: err.message || '' }))
  } finally {
    // doFreshStart 已通过 waitForEnvAlive 路径或直接失败路径内部重置;这里再保险一遍
    isRestarting.value = false
  }
}

// 用户在 picker 里点某个快照
const chooseSnapshot = (snapshot) => {
  // 立刻关闭 picker + 选中快照；异步流程由 watcher 启动
  showSnapshotPicker.value = false
  pickedSnapshot.value = snapshot
}

// 用户在 picker 里点"全新启动"
const chooseFreshStart = () => {
  showSnapshotPicker.value = false
  pickedSnapshot.value = '__FRESH__'
}

// 用户取消 picker
const cancelPickSnapshot = () => {
  showSnapshotPicker.value = false
  availableSnapshots.value = []
  // 重置整个恢复链
  pickedSnapshot.value = null
  isRestarting.value = false
  restartMode.value = null
  recoveryStage.value = 'idle'
  addLog(t('step5.envRestoreCancelled'))
}

// watcher：用户选了快照后启动异步恢复流程
// 这是状态机的核心 —— watcher 解耦 picker UI 和恢复逻辑，无 Promise race
watch(pickedSnapshot, async (newPick) => {
  if (newPick === null) return
  const pick = newPick
  // 用完立刻清掉，避免重复触发
  pickedSnapshot.value = null

  try {
    if (pick === '__FRESH__') {
      recoveryStage.value = 'starting'
      await doFreshStart()
      return
    }

    // 选了一个具体快照
    const targetSnapshot = pick
    addLog(t('step5.envRestoreChosen', { name: targetSnapshot.snapshot_name }))
    // Step 3:恢复选中的快照
    restoringSnapshotName.value = targetSnapshot.snapshot_name  // 给文案 {name} 用
    recoveryStage.value = 'restoring'
    restartMode.value = 'restore'
    const restoreRes = await restoreSnapshot(props.simulationId, {
      snapshot_name: targetSnapshot.snapshot_name
    })
    if (!restoreRes.success) {
      addLog(t('step5.envRestoreFailed', { error: restoreRes.error || '' }))
      resetRestartState()
      return
    }

    // Step 4:启动模拟 (continue 模式 start_round=current_round)
    recoveryStage.value = 'starting'
    addLog(t('step5.envRestartTriggered'))
    const startRes = await startSimulation({
      simulation_id: props.simulationId,
      platform: 'parallel',
      start_round: restoreRes.data?.current_round || 0,
      enable_graph_memory_update: true
    })
    if (startRes.success) {
      recoveryStage.value = 'waiting_alive'
      await waitForEnvAlive()
    } else {
      addLog(t('step5.envRestartFailed', { error: startRes.error || '' }))
      resetRestartState()
    }
  } catch (err) {
    addLog(t('step5.envRestartException', { error: err.message }))
    resetRestartState()
  }
})

// 复位整个恢复状态 (成功/失败后都用)
const resetRestartState = () => {
  isRestarting.value = false
  restartMode.value = null
  recoveryStage.value = 'idle'
  restoringSnapshotName.value = ''
  showSnapshotPicker.value = false
  availableSnapshots.value = []
  pendingSnapshotsForPicker.value = []
  pickedSnapshot.value = null
}

// force 全新启动（force=true 重置 + 可选 start_round 跳过开头几轮）
// opts.startRound:默认 0(从 R0 开始); 设 3 时跳过 R0/R1/R2(用于"从头开始"按钮)
// 返回:true = env 已 alive(成功),false = 后端/超时失败
const doFreshStart = async (opts = {}) => {
  const startRound = opts.startRound ?? 0
  const chatOnly = opts.chatOnly ?? false
  restartMode.value = 'fresh'
  recoveryStage.value = 'starting'
  addLog(t('step5.envFreshTriggered'))
  const res = await startSimulation({
    simulation_id: props.simulationId,
    platform: 'parallel',
    force: true,
    start_round: startRound,  // 0 = 正常从头;3 = 跳过 R0/R1/R2
    enable_graph_memory_update: true,
    chat_only: chatOnly        // True 时后端把 start_round 提到 total_rounds,跳过 rounds 直接进 IPC wait
  })
  if (res.success) {
    recoveryStage.value = 'waiting_alive'
    addLog(t('step5.envRestartTriggered'))
    return await waitForEnvAlive()  // ← 把 waitForEnvAlive 的结果返回
  } else {
    addLog(t('step5.envRestartFailed', { error: res.error || '' }))
    resetRestartState()
    return false
  }
}

// 等待 env 状态变 alive —— 进入循环时打标为 waiting_alive
const waitForEnvAlive = async (maxWaitSec = 30) => {
  recoveryStage.value = 'waiting_alive'
  const startTime = Date.now()
  while (Date.now() - startTime < maxWaitSec * 1000) {
    await new Promise(r => setTimeout(r, 1000))
    await refreshEnvStatus()
    if (envStatus.value === 'alive') {
      addLog(t('step5.envRestartSuccess'))
      flashRestartSuccess()  // ← 短暂绿色 banner,用户能直观看到"已启动"
      resetRestartState()
      return true
    }
  }
  addLog(t('step5.envRestartTimeout'))
  resetRestartState()
  return false
}

// 环境未运行错误检测
const isEnvNotRunningError = (errorMsg) => {
  if (!errorMsg) return false
  const msg = errorMsg.toLowerCase()
  return msg.includes('envNotRunning') ||
         (msg.includes('环境') && msg.includes('运行')) ||
         (msg.includes('environment') && (msg.includes('not running') || msg.includes('not run')))
}

const props = defineProps({
  reportId: String,
  simulationId: String
})

const emit = defineEmits(['add-log', 'update-status', 'go-back'])

// 返回到上一个步骤
// reason: 'env_stopped' → 跳 Step 3 监控(InteractionView 的 handleGoBack 路由)
//         null/undefined → 跳 Step 4
const goBack = (reason = null) => {
  emit('go-back', reason)
}

// State
const activeTab = ref('chat')
const chatTarget = ref('report_agent')
const showAgentDropdown = ref(false)
const selectedAgent = ref(null)
const selectedAgentIndex = ref(null)
const showFullProfile = ref(true)
const showToolsDetail = ref(true)

// Chat State
const chatInput = ref('')
const chatHistory = ref([])
const chatHistoryCache = ref({}) // 缓存所有对话记录: { 'report_agent': [], 'agent_0': [], 'agent_1': [], ... }
const isSending = ref(false)
const chatMessages = ref(null)
const chatInputRef = ref(null)

// Survey State
const selectedAgents = ref(new Set())
const surveyQuestion = ref('')
const surveyResults = ref([])
const isSurveying = ref(false)
// 平台选择器：'both' = 两个平台都问(默认,后端 fan-out,twitter+reddit 各一次 LLM),
// 'reddit' / 'twitter' = 只问一个平台(sendToAgent / submitSurvey 都会透传到后端)。
// 默认 'both' 与历史行为完全一致,不会改变现有用户的体验。
const selectedPlatform = ref('both')

// Report Data
const reportOutline = ref(null)
const generatedSections = ref({})
const collapsedSections = ref(new Set())
const currentSectionIndex = ref(null)
const profiles = ref([])

// Helper Methods
const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

// Refs
const leftPanel = ref(null)
const rightPanel = ref(null)

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const toggleSectionCollapse = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const selectChatTarget = (target) => {
  chatTarget.value = target
  if (target === 'report_agent') {
    showAgentDropdown.value = false
  }
}

// 保存当前对话记录到缓存
const saveChatHistory = () => {
  if (chatHistory.value.length === 0) return
  
  if (chatTarget.value === 'report_agent') {
    chatHistoryCache.value['report_agent'] = [...chatHistory.value]
  } else if (selectedAgentIndex.value !== null) {
    chatHistoryCache.value[`agent_${selectedAgentIndex.value}`] = [...chatHistory.value]
  }
}

const selectReportAgentChat = () => {
  // 保存当前对话记录
  saveChatHistory()
  
  activeTab.value = 'chat'
  chatTarget.value = 'report_agent'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
  
  // 恢复 Report Agent 的对话记录
  chatHistory.value = chatHistoryCache.value['report_agent'] || []
}

const selectSurveyTab = () => {
  activeTab.value = 'survey'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
}

const toggleAgentDropdown = () => {
  showAgentDropdown.value = !showAgentDropdown.value
  if (showAgentDropdown.value) {
    activeTab.value = 'chat'
    chatTarget.value = 'agent'
  }
}

const selectAgent = (agent, idx) => {
  // 保存当前对话记录
  saveChatHistory()
  
  selectedAgent.value = agent
  selectedAgentIndex.value = idx
  chatTarget.value = 'agent'
  showAgentDropdown.value = false
  
  // 恢复该 Agent 的对话记录
  chatHistory.value = chatHistoryCache.value[`agent_${idx}`] || []
  addLog(t('log.selectChatTarget', { name: agent.username }))
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit'
    })
  } catch {
    return ''
  }
}

const renderMarkdown = (content) => {
  if (!content) return ''
  
  let processedContent = content.replace(/^##\s+.+\n+/, '')
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
  
  // 处理列表 - 支持子列表
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })
  
  // 包装无序列表
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // 包装有序列表
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')
  
  // 清理列表项之间的所有空白
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // 清理列表开始标签后的空白
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // 清理列表结束标签前的空白
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  html = '<p class="md-p">' + html + '</p>'
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  // 清理块级元素前后的 <br> 标签
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  // 清理 <p><br> 紧跟块级元素的情况（多余空行导致）
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  // 清理连续的 <br> 标签
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // 清理块级元素后紧跟的段落开始标签前的 <br>
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  // 修复非连续有序列表的编号：当单项 <ol> 被段落内容隔开时，保持编号递增
  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
  html = tokens.join('')

  return html
}

// Chat Methods
const sendMessage = async () => {
  if (!chatInput.value.trim() || isSending.value) return
  
  const message = chatInput.value.trim()
  chatInput.value = ''
  
  // Add user message
  chatHistory.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  })
  
  scrollToBottom()
  isSending.value = true
  
  try {
    if (chatTarget.value === 'report_agent') {
      await sendToReportAgent(message)
    } else {
      await sendToAgent(message)
    }
  } catch (err) {
    addLog(t('log.sendFailed', { error: err.message }))
    chatHistory.value.push({
      role: 'assistant',
      content: t('step5.errorOccurred', { error: err.message }),
      timestamp: new Date().toISOString()
    })
  } finally {
    isSending.value = false
    scrollToBottom()
    // 自动保存对话记录到缓存
    saveChatHistory()
  }
}

const sendToReportAgent = async (message) => {
  if (!props.simulationId) {
    addLog(t('log.noSimulationId'))
    return
  }
  addLog(t('log.sendToReportAgent', { message: message.substring(0, 50) }))
  
  // Build chat history for API
  const historyForApi = chatHistory.value
    .filter(msg => msg.role !== 'user' || msg.content !== message)
    .slice(-10) // Keep last 10 messages
    .map(msg => ({
      role: msg.role,
      content: msg.content
    }))
  
  const res = await chatWithReport({
    simulation_id: props.simulationId,
    message: message,
    chat_history: historyForApi
  })
  
  if (res.success && res.data) {
    chatHistory.value.push({
      role: 'assistant',
      content: res.data.response || res.data.answer || t('step5.noResponse'),
      timestamp: new Date().toISOString()
    })
    addLog(t('log.reportAgentReplied'))
  } else {
    const errorMsg = res.error || t('step5.requestFailed')
    if (isEnvNotRunningError(errorMsg)) {
      throw new Error(t('step5.envNotRunningUser', { error: errorMsg }))
    }
    throw new Error(errorMsg)
  }
}

const sendToAgent = async (message) => {
  if (!props.simulationId) {
    addLog(t('log.noSimulationId'))
    return
  }
  if (!selectedAgent.value || selectedAgentIndex.value === null) {
    throw new Error(t('step5.selectAgentFirst'))
  }
  
  addLog(t('log.sendToAgent', { name: selectedAgent.value.username, message: message.substring(0, 50) }))
  
  // Build prompt with chat history
  let prompt = message
  if (chatHistory.value.length > 1) {
    const historyContext = chatHistory.value
      .filter(msg => msg.content !== message)
      .slice(-6)
      .map(msg => `${msg.role === 'user' ? '提问者' : '你'}：${msg.content}`)
      .join('\n')
    // 追加反 preamble 指令:MiniMax/Qwen 系模型倾向在 answer 之前写
    // "让我思考一下..." 元描述,挤掉真正的回答;在用户问题最后追加直接指令。
    prompt = `以下是我们之前的对话：\n${historyContext}\n\n现在我的新问题是：${message}（请仅给出最终回答,不要任何"让我思考/我需要分析"等前言）`
  }
  
  const res = await interviewAgents({
    simulation_id: props.simulationId,
    // 透传平台选择:'both' 时传 null,后端默认 fan-out 双平台;
    // 'reddit'/'twitter' 时传具体平台,后端只跑那一个,响应时间减半。
    platform: selectedPlatform.value === 'both' ? null : selectedPlatform.value,
    interviews: [{
      agent_id: selectedAgentIndex.value,
      prompt: prompt
    }]
  })
  
  if (res.success && res.data) {
    // 正确的数据路径: res.data.result.results 是一个对象字典
    // 格式: {"reddit_0": {...}, "twitter_0": {...}} 或离线模式 {"both_0": {...}}
    const resultData = res.data.result || res.data
    const resultsDict = resultData.results || resultData

    // 将对象字典转换为结果对象，查找当前 Agent 的回复
    // 修复 "agentResult is not defined" — 把 agentResult 提到分支外,保证
    // 任意分支(对象/数组/缺失)都能在后面的 error 透传里安全引用。
    // 之前 let agentResult 在 if 块级作用域内,Array 分支走完后引用即 ReferenceError。
    let responseContent = null
    let agentResult = null
    const agentId = selectedAgentIndex.value

    if (typeof resultsDict === 'object' && resultsDict !== null && !Array.isArray(resultsDict)) {
      // 尝试多种可能的 key 格式
      const possibleKeys = [
        `reddit_${agentId}`,
        `twitter_${agentId}`,
        `both_${agentId}`
      ]
      for (const key of possibleKeys) {
        if (resultsDict[key]) {
          agentResult = resultsDict[key]
          break
        }
      }
      // 如果没找到特定 key，取第一个可用结果(空对象跳过,避免 agentResult=undefined)
      if (!agentResult && Object.keys(resultsDict).length > 0) {
        agentResult = Object.values(resultsDict)[0]
      }
      if (agentResult) {
        responseContent = agentResult.response || agentResult.answer
      }
    } else if (Array.isArray(resultsDict) && resultsDict.length > 0) {
      // 兼容数组格式 — 同步保存到 agentResult,后续 error 分支也能正常引用
      agentResult = resultsDict[0]
      responseContent = agentResult.response || agentResult.answer
    }

    if (responseContent) {
      chatHistory.value.push({
        role: 'assistant',
        content: responseContent,
        timestamp: new Date().toISOString()
      })
      // 如果是离线模式，添加提示
      if (res.data?.mode === 'offline') {
        addLog(t('log.offlineInterviewMode'))
      }
      addLog(t('log.agentReplied', { name: selectedAgent.value.username }))
    } else if (agentResult && agentResult.error) {
      // 后端 IPC handler 已经把异常写成 result.error,这里显式告诉用户
      throw new Error(
        `Agent ${selectedAgent.value.username} 回应失败(${agentResult.error_type || 'unknown'}): ${agentResult.error}`
      )
    } else {
      throw new Error(t('step5.noResponse'))
    }
  } else if (res.status === 409 || res.data?.busy) {
    // 后端检测到 rounds 还没跑完,直接返 409,前端友好提示
    const cur = res.data?.current_round ?? '?'
    const tot = res.data?.total_rounds ?? '?'
    throw new Error(t('step5.envStoppedBusyHint', { current: cur, total: tot }))
  } else {
    const errorMsg = res.error || t('step5.requestFailed')
    if (isEnvNotRunningError(errorMsg)) {
      throw new Error(t('step5.envNotRunningUser', { error: errorMsg }))
    }
    throw new Error(errorMsg)
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })
}

// Survey Methods
const toggleAgentSelection = (idx) => {
  const newSet = new Set(selectedAgents.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  selectedAgents.value = newSet
}

const selectAllAgents = () => {
  const newSet = new Set()
  profiles.value.forEach((_, idx) => newSet.add(idx))
  selectedAgents.value = newSet
}

const clearAgentSelection = () => {
  selectedAgents.value = new Set()
}

const submitSurvey = async () => {
  if (selectedAgents.value.size === 0 || !surveyQuestion.value.trim()) return
  
  isSurveying.value = true
  addLog(t('log.sendSurvey', { count: selectedAgents.value.size }))

  if (!props.simulationId) {
    addLog(t('log.noSimulationId'))
    isSurveying.value = false
    return
  }

  try {
    const interviews = Array.from(selectedAgents.value).map(idx => ({
      agent_id: idx,
      prompt: surveyQuestion.value.trim()
    }))
    
    const res = await interviewAgents({
      simulation_id: props.simulationId,
      // 透传平台选择(同 sendToAgent)。survey 是 batch interview,顶层 platform 一并透传
      platform: selectedPlatform.value === 'both' ? null : selectedPlatform.value,
      interviews: interviews
    })
    
    if (res.success && res.data) {
      // 正确的数据路径: res.data.result.results 是一个对象字典
      // 格式: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
      const resultData = res.data.result || res.data
      const resultsDict = resultData.results || resultData
      
      // 将对象字典转换为数组格式
      const surveyResultsList = []
      
      for (const interview of interviews) {
        const agentIdx = interview.agent_id
        const agent = profiles.value[agentIdx]
        
        // 优先使用 reddit 平台回复，其次 twitter
        let responseContent = t('step5.noResponse')

        if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
          // 尝试多种可能的 key 格式（兼容在线/离线模式）
          const possibleKeys = [
            `reddit_${agentIdx}`,
            `twitter_${agentIdx}`,
            `both_${agentIdx}`
          ]
          let agentResult = null
          for (const key of possibleKeys) {
            if (resultsDict[key]) {
              agentResult = resultsDict[key]
              break
            }
          }
          if (agentResult) {
            responseContent = agentResult.response || agentResult.answer || t('step5.noResponse')
          }
        } else if (Array.isArray(resultsDict)) {
          // 兼容数组格式
          const matchedResult = resultsDict.find(r => r.agent_id === agentIdx)
          if (matchedResult) {
            responseContent = matchedResult.response || matchedResult.answer || t('step5.noResponse')
          }
        }
        
        surveyResultsList.push({
          agent_id: agentIdx,
          agent_name: agent?.username || `Agent ${agentIdx}`,
          profession: agent?.profession,
          question: surveyQuestion.value.trim(),
          answer: responseContent
        })
      }
      
      surveyResults.value = surveyResultsList
      addLog(t('log.receivedReplies', { count: surveyResults.value.length }))
    } else {
      const errorMsg = res.error || t('step5.requestFailed')
      if (isEnvNotRunningError(errorMsg)) {
        throw new Error(t('step5.envNotRunningUser', { error: errorMsg }))
      }
      throw new Error(errorMsg)
    }
  } catch (err) {
    addLog(t('log.surveySendFailed', { error: err.message }))
  } finally {
    isSurveying.value = false
  }
}

// Load Report Data
const loadReportData = async () => {
  if (!props.reportId) return
  
  try {
    addLog(t('log.loadReportData', { id: props.reportId }))
    
    // Get report info
    const reportRes = await getReport(props.reportId)
    if (reportRes.success && reportRes.data) {
      // Load agent logs to get report outline and sections
      await loadAgentLogs()
    }
  } catch (err) {
    addLog(t('log.loadReportFailed', { error: err.message }))
  }
}

const loadAgentLogs = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, 0)
    if (res.success && res.data) {
      const logs = res.data.logs || []
      
      logs.forEach(log => {
        if (log.action === 'planning_complete' && log.details?.outline) {
          reportOutline.value = log.details.outline
        }
        
        if (log.action === 'section_complete' && log.section_index < 100 && log.details?.content) {
          generatedSections.value[log.section_index] = log.details.content
        }
      })
      
      addLog(t('log.reportDataLoaded'))
    }
  } catch (err) {
    addLog(t('log.loadReportLogFailed', { error: err.message }))
  }
}

const loadProfiles = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId, 'reddit')
    if (res.success && res.data) {
      profiles.value = res.data.profiles || []
      addLog(t('log.loadedProfiles', { count: profiles.value.length }))
    }
  } catch (err) {
    addLog(t('log.loadProfilesFailed', { error: err.message }))
  }
}

// Click outside to close dropdown
const handleClickOutside = (e) => {
  const dropdown = document.querySelector('.agent-dropdown')
  if (dropdown && !dropdown.contains(e.target)) {
    showAgentDropdown.value = false
  }
}

// Lifecycle
onMounted(() => {
  addLog(t('log.step5Init'))
  loadReportData()
  loadProfiles()
  refreshEnvStatus()
  document.addEventListener('click', handleClickOutside)
})

// Watch simulationId changes
watch(() => props.simulationId, (newId) => {
  if (newId) {
    loadProfiles()
    refreshEnvStatus()
  }
}, { immediate: true })

watch(() => props.reportId, (newId) => {
  if (newId) {
    loadReportData()
  }
}, { immediate: true })

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.interaction-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #F8F9FA;
  font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
  overflow: hidden;
}

/* Utility Classes */
.mono {
  font-family: 'JetBrains Mono', 'SF Mono', 'Monaco', 'Consolas', monospace;
}

/* Main Split Layout */
.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Panel - Report Style (与 Step4Report.vue 完全一致) */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: #FFFFFF;
  border-right: 1px solid #E5E7EB;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 30px 50px 60px 50px;
}

.left-panel::-webkit-scrollbar {
  width: 6px;
}

.left-panel::-webkit-scrollbar-track {
  background: transparent;
}

.left-panel::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 3px;
  transition: background 0.3s ease;
}

.left-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
}

.left-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

/* Report Header */
.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block {
  margin-bottom: 30px;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.report-tag {
  background: #000000;
  color: #FFFFFF;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 8px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.report-id {
  font-size: 11px;
  color: #9CA3AF;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.main-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 36px;
  font-weight: 700;
  color: #111827;
  line-height: 1.2;
  margin: 0 0 16px 0;
  letter-spacing: -0.02em;
}

.sub-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 16px;
  color: #6B7280;
  font-style: italic;
  line-height: 1.6;
  margin: 0 0 30px 0;
  font-weight: 400;
}

.header-divider {
  height: 1px;
  background: #E5E7EB;
  width: 100%;
}

/* Sections List */
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  transition: background-color 0.2s ease;
  padding: 8px 12px;
  margin: -8px -12px;
  border-radius: 8px;
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background-color: #F9FAFB;
}

.collapse-icon {
  margin-left: auto;
  color: #9CA3AF;
  transition: transform 0.3s ease;
  flex-shrink: 0;
  align-self: center;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  color: #E5E7EB;
  font-weight: 500;
  transition: color 0.3s ease;
}

.section-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 24px;
  font-weight: 600;
  color: #111827;
  margin: 0;
  transition: color 0.3s ease;
}

/* States */
.report-section-item.is-pending .section-number {
  color: #E5E7EB;
}
.report-section-item.is-pending .section-title {
  color: #D1D5DB;
}

.report-section-item.is-active .section-number,
.report-section-item.is-completed .section-number {
  color: #9CA3AF;
}

.report-section-item.is-active .section-title,
.report-section-item.is-completed .section-title {
  color: #111827;
}

.section-body {
  padding-left: 28px;
  overflow: hidden;
}

/* Generated Content */
.generated-content {
  font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
}

.generated-content :deep(p) {
  margin-bottom: 1em;
}

.generated-content :deep(.md-h2),
.generated-content :deep(.md-h3),
.generated-content :deep(.md-h4) {
  font-family: 'Times New Roman', Times, serif;
  color: #111827;
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 700;
}

.generated-content :deep(.md-h2) { font-size: 20px; border-bottom: 1px solid #F3F4F6; padding-bottom: 8px; }
.generated-content :deep(.md-h3) { font-size: 18px; }
.generated-content :deep(.md-h4) { font-size: 16px; }

.generated-content :deep(.md-ul),
.generated-content :deep(.md-ol) {
  padding-left: 20px;
  margin-bottom: 1em;
}

.generated-content :deep(.md-li) {
  margin-bottom: 0.5em;
}

.generated-content :deep(.md-quote) {
  border-left: 3px solid #E5E7EB;
  padding-left: 16px;
  margin: 1.5em 0;
  color: #6B7280;
  font-style: italic;
  font-family: 'Times New Roman', Times, serif;
}

.generated-content :deep(.code-block) {
  background: #F9FAFB;
  padding: 12px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  overflow-x: auto;
  margin: 1em 0;
  border: 1px solid #E5E7EB;
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: #111827;
}

/* Loading State */
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6B7280;
  font-size: 14px;
  margin-top: 4px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-text {
  font-family: 'Times New Roman', Times, serif;
  font-size: 15px;
  color: #4B5563;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Content Styles Override */
.generated-content :deep(.md-h2) {
  font-family: 'Times New Roman', Times, serif;
  font-size: 18px;
  margin-top: 0;
}

/* Waiting Placeholder */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 40px;
  color: #9CA3AF;
}

.waiting-animation {
  position: relative;
  width: 48px;
  height: 48px;
}

.waiting-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 2px solid #E5E7EB;
  border-radius: 50%;
  animation: ripple 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.4s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes ripple {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.waiting-text {
  font-size: 14px;
}

/* Right Panel - Interaction */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  overflow: hidden;
}

/* Action Bar - Professional Design */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid #E5E7EB;
  background: linear-gradient(180deg, #FFFFFF 0%, #FAFBFC 100%);
  gap: 16px;
}

/* 返回按钮样式 */
.back-step-btn-interaction {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 20px;
  font-size: 13px;
  font-weight: 500;
  color: #6B7280;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 8px;
}

.back-step-btn-interaction:hover {
  background: #F3F4F6;
  border-color: #D1D5DB;
  color: #374151;
}

.back-step-btn-interaction svg {
  transition: transform 0.2s ease;
}

.back-step-btn-interaction:hover svg {
  transform: translateX(-4px);
}

.action-bar-header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 160px;
}

.action-bar-icon {
  color: #1F2937;
  flex-shrink: 0;
}

.action-bar-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.action-bar-title {
  font-size: 13px;
  font-weight: 600;
  color: #1F2937;
  letter-spacing: -0.01em;
}

.action-bar-subtitle {
  font-size: 11px;
  color: #9CA3AF;
}

.action-bar-subtitle.mono {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
}

.action-bar-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  justify-content: flex-end;
}

.tab-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 500;
  color: #6B7280;
  background: #F3F4F6;
  border: 1px solid transparent;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab-pill:hover {
  background: #E5E7EB;
  color: #374151;
}

.tab-pill.active {
  background: #1F2937;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.15);
}

.tab-pill svg {
  flex-shrink: 0;
  opacity: 0.7;
}

.tab-pill.active svg {
  opacity: 1;
}

.tab-divider {
  width: 1px;
  height: 24px;
  background: #E5E7EB;
  margin: 0 6px;
}

.agent-pill {
  width: 200px;
  justify-content: space-between;
}

.agent-pill span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.survey-pill {
  background: #ECFDF5;
  color: #047857;
}

.survey-pill:hover {
  background: #D1FAE5;
  color: #065F46;
}

.survey-pill.active {
  background: #047857;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(4, 120, 87, 0.2);
}

/* Interaction Header */
.interaction-header {
  padding: 16px 24px;
  border-bottom: 1px solid #E5E7EB;
  background: #FAFAFA;
}

.tab-switcher {
  display: flex;
  gap: 8px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #6B7280;
  background: transparent;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: #F9FAFB;
  border-color: #D1D5DB;
}

.tab-btn.active {
  background: #1F2937;
  color: #FFFFFF;
  border-color: #1F2937;
}

.tab-btn svg {
  flex-shrink: 0;
}

/* Chat Container */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Report Agent Tools Card */
.report-agent-tools-card {
  border-bottom: 1px solid #E5E7EB;
  background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
}

.tools-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
}

.tools-card-avatar {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  background: linear-gradient(135deg, #1F2937 0%, #374151 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.2);
}

.tools-card-info {
  flex: 1;
  min-width: 0;
}

.tools-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 2px;
}

.tools-card-subtitle {
  font-size: 12px;
  color: #6B7280;
}

.tools-card-toggle {
  width: 28px;
  height: 28px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6B7280;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.tools-card-toggle:hover {
  background: #F9FAFB;
  border-color: #D1D5DB;
}

.tools-card-toggle svg {
  transition: transform 0.3s ease;
}

.tools-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.tools-card-body {
  padding: 0 20px 16px 20px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.tool-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: #FFFFFF;
  border-radius: 10px;
  border: 1px solid #E5E7EB;
  transition: all 0.2s ease;
}

.tool-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.tool-icon-wrapper {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-purple .tool-icon-wrapper {
  background: rgba(139, 92, 246, 0.1);
  color: #8B5CF6;
}

.tool-blue .tool-icon-wrapper {
  background: rgba(59, 130, 246, 0.1);
  color: #3B82F6;
}

.tool-orange .tool-icon-wrapper {
  background: rgba(249, 115, 22, 0.1);
  color: #F97316;
}

.tool-green .tool-icon-wrapper {
  background: rgba(34, 197, 94, 0.1);
  color: #22C55E;
}

.tool-content {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: 12px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 4px;
}

.tool-desc {
  font-size: 11px;
  color: #6B7280;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Agent Profile Card */
.agent-profile-card {
  border-bottom: 1px solid #E5E7EB;
  background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
}

.profile-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
}

.profile-card-avatar {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  background: linear-gradient(135deg, #1F2937 0%, #374151 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.2);
}

.profile-card-info {
  flex: 1;
  min-width: 0;
}

.profile-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 2px;
}

.profile-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6B7280;
}

.profile-card-handle {
  color: #9CA3AF;
}

.profile-card-profession {
  padding: 2px 8px;
  background: #E5E7EB;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.profile-card-toggle {
  width: 28px;
  height: 28px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6B7280;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.profile-card-toggle:hover {
  background: #F9FAFB;
  border-color: #D1D5DB;
}

.profile-card-toggle svg {
  transition: transform 0.3s ease;
}

.profile-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.profile-card-body {
  padding: 0 20px 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.profile-card-label {
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.profile-card-bio {
  background: #FFFFFF;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid #E5E7EB;
}

.profile-card-bio p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4B5563;
}

/* Target Selector */
.target-selector {
  padding: 16px 24px;
  border-bottom: 1px solid #E5E7EB;
}

.selector-label {
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}

.selector-options {
  display: flex;
  gap: 12px;
}

.target-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.target-option:hover {
  border-color: #D1D5DB;
}

.target-option.active {
  background: #1F2937;
  color: #FFFFFF;
  border-color: #1F2937;
}

/* Agent Dropdown */
.agent-dropdown {
  position: relative;
}

.dropdown-arrow {
  margin-left: 4px;
  transition: transform 0.2s ease;
  opacity: 0.6;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 240px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12), 0 4px 12px rgba(0, 0, 0, 0.06);
  max-height: 320px;
  overflow-y: auto;
  z-index: 100;
}

.dropdown-header {
  padding: 12px 16px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #F3F4F6;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  border-left: 3px solid transparent;
}

.dropdown-item:hover {
  background: #F9FAFB;
  border-left-color: #1F2937;
}

.dropdown-item:first-of-type {
  margin-top: 4px;
}

.dropdown-item:last-child {
  margin-bottom: 4px;
}

.agent-avatar {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  background: linear-gradient(135deg, #1F2937 0%, #374151 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(31, 41, 55, 0.1);
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: #1F2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-role {
  font-size: 11px;
  color: #9CA3AF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Chat Messages */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #9CA3AF;
}

.empty-icon {
  opacity: 0.3;
}

.empty-text {
  font-size: 14px;
  text-align: center;
  max-width: 280px;
  line-height: 1.6;
}

.chat-message {
  display: flex;
  gap: 12px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.chat-message.user .message-avatar {
  background: #1F2937;
  color: #FFFFFF;
}

.chat-message.assistant .message-avatar {
  background: #F3F4F6;
  color: #374151;
}

.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-message.user .message-content {
  align-items: flex-end;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-message.user .message-header {
  flex-direction: row-reverse;
}

.sender-name {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.message-time {
  font-size: 11px;
  color: #9CA3AF;
}

.message-text {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.chat-message.user .message-text {
  background: #1F2937;
  color: #FFFFFF;
  border-bottom-right-radius: 4px;
}

.chat-message.assistant .message-text {
  background: #F3F4F6;
  color: #374151;
  border-bottom-left-radius: 4px;
}

.message-text :deep(.md-p) {
  margin: 0;
}

.message-text :deep(.md-p:last-child) {
  margin-bottom: 0;
}

/* 修复有序列表编号 - 使用 CSS 计数器让多个 ol 连续编号 */
.message-text {
  counter-reset: list-counter;
}

.message-text :deep(.md-ol) {
  list-style: none;
  padding-left: 0;
  margin: 8px 0;
}

.message-text :deep(.md-oli) {
  counter-increment: list-counter;
  display: flex;
  gap: 8px;
  margin: 4px 0;
}

.message-text :deep(.md-oli)::before {
  content: counter(list-counter) ".";
  font-weight: 600;
  color: #374151;
  min-width: 20px;
  flex-shrink: 0;
}

/* 无序列表样式 */
.message-text :deep(.md-ul) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-text :deep(.md-li) {
  margin: 4px 0;
}

/* Typing Indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: #F3F4F6;
  border-radius: 12px;
  border-bottom-left-radius: 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #9CA3AF;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) { animation-delay: 0s; }
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

/* Chat Input */
.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid #E5E7EB;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

/* 模拟世界停止时的内嵌横幅 —— 用户在聊天输入处就能看到 */
.chat-stopped-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
  border: 1px solid #FFB74D;
  border-radius: 6px;
  font-size: 12px;
}

.chat-stopped-icon {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 1;
}

.chat-stopped-text {
  flex: 1;
  color: #E65100;
  font-weight: 500;
  line-height: 1.4;
}

.chat-stopped-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #FF6F00;
  color: #FFFFFF;
  border: 1px solid #FF6F00;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.chat-stopped-btn:hover:not(:disabled) {
  background: #E65100;
  border-color: #E65100;
}

.chat-stopped-btn:disabled {
  background: #FFB74D;
  border-color: #FFB74D;
  cursor: not-allowed;
}

/* Chat-Only 次级按钮:跟主按钮并排,视觉权重稍低,提示用户"轻量启动"选项 */
.chat-stopped-btn-secondary {
  background: #FFFFFF;
  color: #FF6F00;
  border: 1px solid #FFB74D;
}
.chat-stopped-btn-secondary:hover:not(:disabled) {
  background: #FFF3E0;
  border-color: #FF6F00;
  color: #E65100;
}

.chat-input {
  flex: 1;
  padding: 12px 16px;
  font-size: 14px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s ease;
}

.chat-input:focus {
  outline: none;
  border-color: #1F2937;
}

.chat-input:disabled {
  background: #F9FAFB;
  cursor: not-allowed;
}

.send-btn {
  width: 44px;
  height: 44px;
  background: #1F2937;
  color: #FFFFFF;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  background: #374151;
}

.send-btn:disabled {
  background: #E5E7EB;
  color: #9CA3AF;
  cursor: not-allowed;
}

/* 平台选择器:三个 pill 横排,放 chat 输入行内 + survey 提交按钮上方 */
.platform-selector {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  background: #F3F4F6;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  flex-shrink: 0;
  align-self: flex-end;
  margin-bottom: 4px;
}

.platform-selector-survey {
  align-self: flex-start;
  margin-bottom: 0;
  margin-top: 4px;
}

.platform-pill {
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  color: #6B7280;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  font-family: inherit;
  line-height: 1.4;
}

.platform-pill:hover:not(:disabled):not(.active) {
  background: #FFFFFF;
  color: #1F2937;
}

.platform-pill.active {
  background: #1F2937;
  color: #FFFFFF;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.platform-pill:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Survey Container */
.survey-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.survey-setup {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-bottom: 1px solid #E5E7EB;
  overflow: hidden;
}

.setup-section {
  margin-bottom: 24px;
}

.setup-section:first-child {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.setup-section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.setup-section .section-header .section-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.selection-count {
  font-size: 12px;
  color: #9CA3AF;
}

/* Agents Grid */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  flex: 1;
  overflow-y: auto;
  padding: 4px;
  align-content: start;
}

.agent-checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.agent-checkbox:hover {
  border-color: #D1D5DB;
}

.agent-checkbox.checked {
  background: #F0FDF4;
  border-color: #10B981;
}

.agent-checkbox input {
  display: none;
}

.checkbox-avatar {
  width: 28px;
  height: 28px;
  min-width: 28px;
  min-height: 28px;
  background: #E5E7EB;
  color: #374151;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.agent-checkbox.checked .checkbox-avatar {
  background: #10B981;
  color: #FFFFFF;
}

.checkbox-info {
  flex: 1;
  min-width: 0;
}

.checkbox-name {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #1F2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-role {
  display: block;
  font-size: 10px;
  color: #9CA3AF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-indicator {
  width: 20px;
  height: 20px;
  border: 2px solid #E5E7EB;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.agent-checkbox.checked .checkbox-indicator {
  background: #10B981;
  border-color: #10B981;
  color: #FFFFFF;
}

.checkbox-indicator svg {
  opacity: 0;
  transform: scale(0.5);
  transition: all 0.2s ease;
}

.agent-checkbox.checked .checkbox-indicator svg {
  opacity: 1;
  transform: scale(1);
}

.selection-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.action-link {
  font-size: 12px;
  color: #6B7280;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.action-link:hover {
  color: #1F2937;
  text-decoration: underline;
}

.action-divider {
  color: #E5E7EB;
}

/* Survey Input */
.survey-input {
  width: 100%;
  padding: 14px 16px;
  font-size: 14px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s ease;
}

.survey-input:focus {
  outline: none;
  border-color: #1F2937;
}

.survey-submit-btn {
  width: 100%;
  padding: 14px 24px;
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
  background: #1F2937;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
}

.survey-submit-btn:hover:not(:disabled) {
  background: #374151;
}

.survey-submit-btn:disabled {
  background: #E5E7EB;
  color: #9CA3AF;
  cursor: not-allowed;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #FFFFFF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Survey Results */
.survey-results {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.results-title {
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
}

.results-count {
  font-size: 12px;
  color: #9CA3AF;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-card {
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 20px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  background: #1F2937;
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-name {
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
}

.result-role {
  font-size: 12px;
  color: #9CA3AF;
}

.result-question {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  background: #FFFFFF;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #6B7280;
}

.result-question svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.result-answer {
  font-size: 14px;
  line-height: 1.7;
  color: #374151;
}

/* Markdown Styles */
:deep(.md-p) {
  margin: 0 0 12px 0;
}

:deep(.md-h2) {
  font-size: 20px;
  font-weight: 700;
  color: #1F2937;
  margin: 24px 0 12px 0;
}

:deep(.md-h3) {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  margin: 20px 0 10px 0;
}

:deep(.md-h4) {
  font-size: 14px;
  font-weight: 600;
  color: #4B5563;
  margin: 16px 0 8px 0;
}

:deep(.md-h5) {
  font-size: 13px;
  font-weight: 600;
  color: #6B7280;
  margin: 12px 0 6px 0;
}

:deep(.md-ul), :deep(.md-ol) {
  margin: 12px 0;
  padding-left: 24px;
}

:deep(.md-li), :deep(.md-oli) {
  margin: 6px 0;
}

/* 聊天/问卷区域的引用样式 */
.chat-messages :deep(.md-quote),
.result-answer :deep(.md-quote) {
  margin: 12px 0;
  padding: 12px 16px;
  background: #F9FAFB;
  border-left: 3px solid #1F2937;
  color: #4B5563;
}

:deep(.code-block) {
  margin: 12px 0;
  padding: 12px 16px;
  background: #1F2937;
  border-radius: 6px;
  overflow-x: auto;
}

:deep(.code-block code) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #E5E7EB;
}

:deep(.inline-code) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  background: #F3F4F6;
  padding: 2px 6px;
  border-radius: 4px;
  color: #1F2937;
}

:deep(.md-hr) {
  border: none;
  border-top: 1px solid #E5E7EB;
  margin: 24px 0;
}

/* Environment Status Bar */
.env-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 0 16px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  background: #F5F5F5;
}

.env-status-bar.alive {
  background: #E8F5E9;
  color: #2E7D32;
}

.env-status-action {
  margin-left: auto;
  padding: 4px 10px;
  border: 1px solid #FFB74D;
  background: #FFF3E0;
  color: #E65100;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.env-status-action:hover {
  background: #FFE0B2;
  border-color: #FB8C00;
}

/* 次级按钮 —— 强制从头开始,样式比主入口稍弱以免抢镜 */
.env-status-action-force {
  background: #FFF;
  color: #757575;
  border-color: #DDDDDD;
  margin-left: 6px;   /* 紧贴主按钮右侧 */
}

.env-status-action-force:hover {
  background: #FAFAFA;
  border-color: #BDBDBD;
  color: #424242;
}

/* 多快照选择器（≥2 个 final_/fail_ 快照时） */
.snapshot-picker {
  margin: 0 16px 12px;
  padding: 12px;
  background: #FFF8E1;
  border: 1px solid #FFB74D;
  border-radius: 6px;
  font-size: 12px;
}

.snapshot-picker-title {
  font-weight: 600;
  color: #E65100;
  margin-bottom: 4px;
}

.snapshot-picker-hint {
  color: #666;
  margin-bottom: 8px;
  font-size: 11px;
}

/* 自动倒计时 banner —— 5s 不选就自动 force fresh,减少点击次数 */
.snapshot-picker-countdown {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #FFF8E1;
  border: 1px solid #FFE082;
  border-radius: 4px;
  margin-bottom: 10px;
  font-size: 11px;
  color: #E65100;
  font-weight: 500;
}

.snapshot-picker-countdown .countdown-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #FF6F00;
  animation: env-spin 1s linear infinite reverse;
  flex-shrink: 0;
}

.snapshot-picker-countdown .countdown-skip {
  margin-left: auto;
  padding: 3px 10px;
  background: #FF6F00;
  color: #FFFFFF;
  border: none;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.snapshot-picker-countdown .countdown-skip:hover {
  background: #E65100;
}

/* 重启成功短暂绿色 banner —— 4s 自动消失 */
.restart-success-banner {
  margin: 0 16px 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
  border: 1px solid #81C784;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #2E7D32;
  font-weight: 600;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(76, 175, 80, 0.15);
}

.restart-success-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #4CAF50;
  color: #FFFFFF;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}

.restart-success-text {
  flex: 1;
}

.restart-success-enter-active,
.restart-success-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.restart-success-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.restart-success-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.snapshot-picker-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.snapshot-picker-item {
  padding: 8px 10px;
  background: #FFF;
  border: 1px solid #FFE0B2;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.snapshot-picker-item:hover {
  background: #FFF3E0;
  border-color: #FB8C00;
}

.snapshot-picker-item-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
  color: #333;
}

.snapshot-picker-item-meta {
  font-size: 11px;
  color: #888;
  display: flex;
  gap: 8px;
}

.snapshot-picker-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.snapshot-picker-btn {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #DDD;
  background: #FFF;
  color: #666;
  transition: all 0.15s;
}

.snapshot-picker-btn:hover {
  background: #F5F5F5;
}

.snapshot-picker-btn.fresh {
  border-color: #FF9800;
  color: #E65100;
}

.snapshot-picker-btn.cancel {
  border-color: #DDD;
  color: #999;
}

.env-status-bar.stopped {
  background: #FFF3E0;
  color: #E65100;
}

.env-status-bar.unknown,
.env-status-bar.null {
  background: #F5F5F5;
  color: #757575;
}

.env-loading {
  animation: pulse 1s infinite;
}

.env-status-dot {
  font-size: 14px;
  line-height: 1;
}

/*（已删除 env-recovery-progress / -spinner / -stage —— 大 banner 已取代小转圈，避免双指示） */

@keyframes env-spin {
  to { transform: rotate(360deg); }
}

/*（已删除 picker 的 is-disabled 样式 —— picker 必须保持可点击，由 closeSnapshotPicker 自动防重）*/

/* 恢复期进度区:替换 picker 的大型 banner,用户绝对不可能错过反馈 */
.restart-progress-area {
  margin: 0 16px 12px;
  border-radius: 8px;
  overflow: hidden;
}

.restart-progress-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
  border: 1px solid #FFB74D;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(255, 152, 0, 0.15);
}

.restart-progress-banner.stage-restoring,
.restart-progress-banner.stage-starting,
.restart-progress-banner.stage-waiting_alive {
  background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
  border-color: #64B5F6;
  box-shadow: 0 2px 8px rgba(33, 150, 243, 0.15);
}

.restart-progress-spinner {
  display: inline-block;
  width: 28px;
  height: 28px;
  min-width: 28px;
  border: 3px solid rgba(230, 81, 0, 0.2);
  border-top-color: #E65100;
  border-radius: 50%;
  animation: env-spin 0.7s linear infinite;
  flex-shrink: 0;
}

.restart-progress-banner.stage-restoring .restart-progress-spinner,
.restart-progress-banner.stage-starting .restart-progress-spinner,
.restart-progress-banner.stage-waiting_alive .restart-progress-spinner {
  border-color: rgba(33, 150, 243, 0.2);
  border-top-color: #1976D2;
}

.restart-progress-content {
  flex: 1;
  min-width: 0;
}

.restart-progress-stage {
  font-size: 13px;
  font-weight: 700;
  color: #E65100;
  margin-bottom: 2px;
}

.restart-progress-banner.stage-restoring .restart-progress-stage,
.restart-progress-banner.stage-starting .restart-progress-stage,
.restart-progress-banner.stage-waiting_alive .restart-progress-stage {
  color: #0D47A1;
}

.restart-progress-hint {
  font-size: 11px;
  color: #BF360C;
  line-height: 1.4;
}

.restart-progress-banner.stage-restoring .restart-progress-hint,
.restart-progress-banner.stage-starting .restart-progress-hint,
.restart-progress-banner.stage-waiting_alive .restart-progress-hint {
  color: #1565C0;
}

.env-alive { color: #4CAF50; }
.env-stopped { color: #FF9800; }
.env-unknown { color: #9E9E9E; }
.env-loading { color: #666; }
</style>

<style>
/* English locale: smaller report title */
html[lang="en"] .report-header-block .main-title {
  font-size: 28px;
}
</style>
