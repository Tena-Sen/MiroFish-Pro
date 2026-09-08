<template>
  <div class="simulation-panel">
    <!-- Top Control Bar -->
    <div class="control-bar">
      <div class="status-group">
        <!-- Twitter 平台进度 -->
        <div class="platform-status twitter" :class="{ active: runStatus.twitter_running, completed: runStatus.twitter_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
            <span class="platform-name">Info Plaza</span>
            <span v-if="runStatus.twitter_completed" class="status-badge">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">ROUND</span>
              <span class="stat-value mono">{{ runStatus.twitter_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">TIME</span>
              <span class="stat-value mono">{{ twitterElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">ACTS</span>
              <span class="stat-value mono">{{ runStatus.twitter_actions_count || 0 }}</span>
            </span>
          </div>
          <!-- T1：本轮增量（仅当有新增时显示） -->
          <div v-if="twitterRoundDelta > 0" class="round-delta-pill twitter">
            <span class="round-delta-icon">▲</span>
            <span class="round-delta-text">+{{ twitterRoundDelta }} this round</span>
          </div>
          <!-- 可用动作提示 -->
          <div class="actions-tooltip">
            <div class="tooltip-title">Available Actions</div>
            <div class="tooltip-actions">
              <span class="tooltip-action">POST</span>
              <span class="tooltip-action">LIKE</span>
              <span class="tooltip-action">REPOST</span>
              <span class="tooltip-action">QUOTE</span>
              <span class="tooltip-action">FOLLOW</span>
              <span class="tooltip-action">IDLE</span>
            </div>
          </div>
        </div>
        
        <!-- Reddit 平台进度 -->
        <div class="platform-status reddit" :class="{ active: runStatus.reddit_running, completed: runStatus.reddit_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
            <span class="platform-name">Topic Community</span>
            <span v-if="runStatus.reddit_completed" class="status-badge">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">ROUND</span>
              <span class="stat-value mono">{{ runStatus.reddit_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">TIME</span>
              <span class="stat-value mono">{{ redditElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">ACTS</span>
              <span class="stat-value mono">{{ runStatus.reddit_actions_count || 0 }}</span>
            </span>
          </div>
          <!-- T1：本轮增量 -->
          <div v-if="redditRoundDelta > 0" class="round-delta-pill reddit">
            <span class="round-delta-icon">▲</span>
            <span class="round-delta-text">+{{ redditRoundDelta }} this round</span>
          </div>
          <!-- 可用动作提示 -->
          <div class="actions-tooltip">
            <div class="tooltip-title">Available Actions</div>
            <div class="tooltip-actions">
              <span class="tooltip-action">POST</span>
              <span class="tooltip-action">COMMENT</span>
              <span class="tooltip-action">LIKE</span>
              <span class="tooltip-action">DISLIKE</span>
              <span class="tooltip-action">SEARCH</span>
              <span class="tooltip-action">TREND</span>
              <span class="tooltip-action">FOLLOW</span>
              <span class="tooltip-action">MUTE</span>
              <span class="tooltip-action">REFRESH</span>
              <span class="tooltip-action">IDLE</span>
            </div>
          </div>
        </div>
      </div>

      <div class="action-controls">
        <button
          class="action-btn primary"
          :disabled="phase !== 2 || isGeneratingReport"
          @click="handleNextStep"
        >
          <span v-if="isGeneratingReport" class="loading-spinner-small"></span>
          {{ isGeneratingReport ? $t('step3.generatingReportBtn') : $t('step3.startGenerateReportBtn') }}
          <span v-if="!isGeneratingReport" class="arrow-icon">→</span>
        </button>

        <!-- 快照管理按钮 -->
        <button
          class="action-btn secondary"
          @click="handleListSnapshots"
          :title="$t('step3.manageSnapshots')"
        >
          <svg class="btn-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
            <polyline points="17 21 17 13 7 13 7 21"></polyline>
            <polyline points="7 3 7 8 15 8"></polyline>
          </svg>
          {{ $t('step3.snapshots') }}
        </button>
      </div>
    </div>

    <!-- 后端异常横幅：连续失败 ≥ 3 次时显示 -->
    <div v-if="pollErrorBanner" class="poll-error-banner">
      <span class="banner-icon">⚠️</span>
      <span class="banner-text">{{ pollErrorBanner }}</span>
      <button class="banner-dismiss" @click="pollErrorBanner = ''">✕</button>
    </div>

    <!-- 自动恢复提示 — 当检测到有上一次完成的模拟快照时显示 -->
    <div class="auto-restore-prompt" v-if="showAutoRestorePrompt && latestSnapshotForRestore">
      <div class="prompt-content">
        <svg class="prompt-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <div class="prompt-text">
          <span class="prompt-title">发现上一次模拟快照</span>
          <span class="prompt-desc">检测到上次模拟的快照 <strong>{{ latestSnapshotForRestore.snapshot_name }}</strong>，是否恢复后继续？</span>
        </div>
      </div>
      <div class="prompt-actions">
        <button class="prompt-btn primary" @click="handleContinueAutoRestore">
          恢复并继续
        </button>
        <button class="prompt-btn secondary" @click="handleIgnoreAutoRestore">
          忽略
        </button>
      </div>
    </div>

    <!-- 轮数选择提示 — 直接进入 Step3 全新启动时，先询问本次模拟轮数 -->
    <div class="auto-restore-prompt rounds-prompt" v-if="showRoundsPrompt">
      <div class="prompt-content">
        <svg class="prompt-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
        <div class="prompt-text">
          <span class="prompt-title">{{ $t('step3.roundsPromptTitle') }}</span>
          <span class="prompt-desc">
            {{ roundsConfigLoading ? $t('step3.roundsPromptLoading') : $t('step3.roundsPromptDesc', { rounds: promptAutoRounds || 40 }) }}
          </span>
        </div>
        <input
          type="number"
          class="rounds-input"
          v-model.number="promptRounds"
          min="10"
          :max="promptAutoRounds || undefined"
          :disabled="roundsConfigLoading"
        />
      </div>
      <div class="prompt-actions">
        <button class="prompt-btn primary" :disabled="roundsConfigLoading" @click="handleRoundsPromptConfirm">
          {{ $t('step3.roundsPromptStart') }}
        </button>
        <button class="prompt-btn secondary" @click="handleRoundsPromptCancel">
          {{ $t('step3.roundsPromptCancel') }}
        </button>
      </div>
    </div>

    <!-- 轮数选择被取消后：保留重新配置入口，避免无法启动 -->
    <div class="auto-restore-prompt" v-if="roundsPromptDismissed && !showRoundsPrompt && phase === 0 && !isStarting">
      <div class="prompt-content">
        <svg class="prompt-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <div class="prompt-text">
          <span class="prompt-title">{{ $t('step3.roundsDismissedTitle') }}</span>
          <span class="prompt-desc">{{ $t('step3.roundsDismissedDesc') }}</span>
        </div>
      </div>
      <div class="prompt-actions">
        <button class="prompt-btn primary" @click="reopenRoundsPrompt">
          {{ $t('step3.roundsPromptStart') }}
        </button>
      </div>
    </div>

    <!-- Main Content: Dual Timeline -->
    <div class="main-content-area" ref="scrollContainer">
      <!-- Timeline Header -->
      <div class="timeline-header" v-if="allActions.length > 0">
        <div class="timeline-stats">
          <span class="total-count">TOTAL EVENTS: <span class="mono">{{ allActions.length }}</span></span>
          <span class="platform-breakdown">
            <span class="breakdown-item twitter">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
              <span class="mono">{{ twitterActionsCount }}</span>
            </span>
            <span class="breakdown-divider">/</span>
            <span class="breakdown-item reddit">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
              <span class="mono">{{ redditActionsCount }}</span>
            </span>
          </span>
        </div>
      </div>
      
      <!-- Timeline Feed -->
      <div class="timeline-feed">
        <div class="timeline-axis"></div>
        
        <TransitionGroup name="timeline-item">
          <div 
            v-for="action in chronologicalActions" 
            :key="action._uniqueId || action.id || `${action.timestamp}-${action.agent_id}`" 
            class="timeline-item"
            :class="action.platform"
          >
            <div class="timeline-marker">
              <div class="marker-dot"></div>
            </div>
            
            <div class="timeline-card">
              <div class="card-header">
                <div class="agent-info">
                  <div class="avatar-placeholder">{{ (action.agent_name || 'A')[0] }}</div>
                  <span class="agent-name">{{ action.agent_name }}</span>
                </div>
                
                <div class="header-meta">
                  <div class="platform-indicator">
                    <svg v-if="action.platform === 'twitter'" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                    <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                  </div>
                  <div class="action-badge" :class="getActionTypeClass(action.action_type)">
                    {{ getActionTypeLabel(action.action_type) }}
                  </div>
                </div>
              </div>
              
              <div class="card-body">
                <!-- CREATE_POST: 发布帖子 -->
                <div v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text main-text">
                  {{ action.action_args.content }}
                </div>

                <!-- QUOTE_POST: 引用帖子 -->
                <template v-if="action.action_type === 'QUOTE_POST'">
                  <div v-if="action.action_args?.quote_content" class="content-text">
                    {{ action.action_args.quote_content }}
                  </div>
                  <div v-if="action.action_args?.original_content" class="quoted-block">
                    <div class="quote-header">
                      <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                      <span class="quote-label">@{{ action.action_args.original_author_name || 'User' }}</span>
                    </div>
                    <div class="quote-text">
                      {{ truncateContent(action.action_args.original_content, 150) }}
                    </div>
                  </div>
                </template>

                <!-- REPOST: 转发帖子 -->
                <template v-if="action.action_type === 'REPOST'">
                  <div class="repost-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>
                    <span class="repost-label">Reposted from @{{ action.action_args?.original_author_name || 'User' }}</span>
                  </div>
                  <div v-if="action.action_args?.original_content" class="repost-content">
                    {{ truncateContent(action.action_args.original_content, 200) }}
                  </div>
                </template>

                <!-- LIKE_POST: 点赞帖子 -->
                <template v-if="action.action_type === 'LIKE_POST'">
                  <div class="like-info">
                    <svg class="icon-small filled" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    <span class="like-label">Liked @{{ action.action_args?.post_author_name || 'User' }}'s post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="liked-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- CREATE_COMMENT: 发表评论 -->
                <template v-if="action.action_type === 'CREATE_COMMENT'">
                  <div v-if="action.action_args?.content" class="content-text">
                    {{ action.action_args.content }}
                  </div>
                  <div v-if="action.action_args?.post_id" class="comment-context">
                    <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    <span>Reply to post #{{ action.action_args.post_id }}</span>
                  </div>
                </template>

                <!-- SEARCH_POSTS: 搜索帖子 -->
                <template v-if="action.action_type === 'SEARCH_POSTS'">
                  <div class="search-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <span class="search-label">Search Query:</span>
                    <span class="search-query">"{{ action.action_args?.query || '' }}"</span>
                  </div>
                </template>

                <!-- FOLLOW: 关注用户 -->
                <template v-if="action.action_type === 'FOLLOW'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                    <span class="follow-label">Followed @{{ action.action_args?.target_user_name || action.action_args?.target_user || action.action_args?.user_id || 'User' }}</span>
                  </div>
                </template>

                <!-- UPVOTE / DOWNVOTE / DISLIKE: 帖子投票 -->
                <template v-if="['UPVOTE_POST', 'DOWNVOTE_POST', 'DISLIKE_POST'].includes(action.action_type)">
                  <div class="vote-info">
                    <svg v-if="action.action_type === 'UPVOTE_POST'" class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"></polyline></svg>
                    <svg v-else class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span class="vote-label">
                      {{ action.action_type === 'UPVOTE_POST' ? 'Upvoted' : (action.action_type === 'DOWNVOTE_POST' ? 'Downvoted' : 'Disliked') }}
                      @{{ action.action_args?.post_author_name || 'User' }}'s post
                    </span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="voted-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- LIKE_COMMENT / DISLIKE_COMMENT: 评论投票 -->
                <template v-if="action.action_type === 'LIKE_COMMENT' || action.action_type === 'DISLIKE_COMMENT'">
                  <div class="vote-info">
                    <svg v-if="action.action_type === 'LIKE_COMMENT'" class="icon-small filled" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    <svg v-else class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    <span class="vote-label">{{ action.action_type === 'LIKE_COMMENT' ? 'Liked' : 'Disliked' }} @{{ action.action_args?.comment_author_name || 'User' }}'s comment</span>
                  </div>
                  <div v-if="action.action_args?.comment_content" class="voted-content">
                    "{{ truncateContent(action.action_args.comment_content, 120) }}"
                  </div>
                </template>

                <!-- MUTE: 屏蔽用户 -->
                <template v-if="action.action_type === 'MUTE'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>
                    <span class="follow-label">Muted @{{ action.action_args?.target_user_name || action.action_args?.user_id || 'User' }}</span>
                  </div>
                </template>

                <!-- SEARCH_USER: 搜索用户 -->
                <template v-if="action.action_type === 'SEARCH_USER'">
                  <div class="search-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <span class="search-label">Search User:</span>
                    <span class="search-query">"{{ action.action_args?.query || action.action_args?.user_name || '' }}"</span>
                  </div>
                </template>

                <!-- TREND: 查看热榜 -->
                <template v-if="action.action_type === 'TREND'">
                  <div class="idle-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
                    <span class="idle-label">Checked Trending Topics</span>
                  </div>
                </template>

                <!-- DO_NOTHING: 无操作（静默） -->
                <template v-if="action.action_type === 'DO_NOTHING'">
                  <div class="idle-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <span class="idle-label">Action Skipped</span>
                  </div>
                </template>

                <!-- 通用回退：未知类型，或已知类型但 enrich 字段缺失导致正文为空。
                     有 content 显示内容，否则显示动作类型，保证卡片永不空白 -->
                <div v-if="!knownActionTypes.includes(action.action_type) || isCardBodyEmpty(action)" class="content-text">
                  <template v-if="action.action_args?.content">{{ action.action_args.content }}</template>
                  <template v-else>{{ getActionTypeLabel(action.action_type) }}</template>
                </div>
              </div>

              <div class="card-footer">
                <span class="time-tag">R{{ action.round_num }} • {{ formatActionTime(action.timestamp) }}</span>
                <!-- Platform tag removed as it is in header now -->
              </div>
            </div>
          </div>
        </TransitionGroup>

        <div v-if="allActions.length === 0" class="waiting-state">
          <div class="pulse-ring"></div>
          <span>Waiting for agent actions...</span>
        </div>
      </div>
    </div>

    <!-- Snapshot Management Panel -->
    <div v-if="showSnapshotPanel" class="snapshot-panel">
      <div class="snapshot-panel-header">
        <span class="snapshot-title">{{ $t('step3.snapshotPanelTitle') }}</span>
        <button class="snapshot-close-btn" @click="showSnapshotPanel = false">×</button>
      </div>

      <!-- Create Snapshot Form -->
      <div class="snapshot-create-section">
        <div class="create-form">
          <input
            v-model="snapshotName"
            :placeholder="$t('step3.snapshotNamePlaceholder')"
            class="snapshot-name-input"
            @keyup.enter="handleCreateSnapshot"
          />
          <button
            class="create-snapshot-btn"
            :disabled="isCreatingSnapshot || !props.simulationId"
            @click="handleCreateSnapshot"
          >
            <span v-if="isCreatingSnapshot" class="loading-spinner-small"></span>
            {{ $t('step3.createSnapshotBtn') }}
          </button>
        </div>
        <p class="create-hint">{{ $t('step3.snapshotCreateHint') }}</p>
      </div>

      <!-- Snapshot List -->
      <div class="snapshot-list-section" v-if="snapshots.length > 0 && !showRestoreChoice">
        <div class="snapshot-list-header">{{ $t('step3.snapshotListHeader') }} ({{ snapshots.length }})</div>
        <div class="snapshot-list">
          <div
            v-for="snapshot in snapshots"
            :key="snapshot.snapshot_name"
            class="snapshot-item"
          >
            <div class="snapshot-info">
              <div class="snapshot-name">{{ snapshot.snapshot_name }}</div>
              <div class="snapshot-time">{{ snapshot.created_at }}</div>
              <div class="snapshot-stats" v-if="snapshot.run_state">
                <span class="stat-badge">
                  {{ $t('step3.snapshotStatRound', { current: snapshot.run_state.current_round || 0, total: snapshot.run_state.total_rounds || 0 }) }}
                </span>
                <span class="stat-badge">
                  {{ snapshot.run_state.total_actions_count || 0 }} {{ $t('step3.snapshotStatActions') }}
                </span>
              </div>
            </div>
            <div class="snapshot-actions">
              <button
                class="snapshot-action-btn restore"
                :disabled="isRestoringSnapshot"
                @click="handleRestoreSnapshot(snapshot)"
                :title="$t('step3.restoreSnapshot')"
              >
                ↻
              </button>
              <button
                class="snapshot-action-btn delete"
                :disabled="isDeletingSnapshot"
                @click="handleDeleteSnapshot(snapshot.snapshot_name)"
                :title="$t('step3.deleteSnapshot')"
              >
                🗑
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Restore Choice Dialog - 独立于快照面板，始终可见当 showRestoreChoice 为 true 时 -->
      <div v-if="showRestoreChoice" class="restore-choice-overlay">
        <div class="restore-choice-dialog">
          <h3>{{ $t('log.snapshotRestoreChooseTitle') }}</h3>
          <p class="restore-choice-hint">{{ selectedSnapshot?.snapshot_name }}</p>
          <div class="restore-choice-options">
            <label class="restore-choice-option">
              <input type="radio" name="restoreMode" value="continue" v-model="restoreMode" />
              <span class="option-label">{{ snapshotContinueLabel(selectedSnapshot) }}</span>
            </label>
            <label class="restore-choice-option">
              <input type="radio" name="restoreMode" value="start_over" v-model="restoreMode" />
              <span class="option-label">{{ $t('log.snapshotRestoreStartOver') }}</span>
            </label>
          </div>
          <div class="restore-choice-actions">
            <button class="btn-cancel" @click="handleCancelRestore">{{ $t('common.cancel') }}</button>
            <button class="btn-confirm" @click="doRestoreSnapshot">{{ $t('common.confirm') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Snapshot Empty State - 只在快照面板显示且没有快照时显示 -->
    <div v-if="showSnapshotPanel && snapshots.length === 0" class="snapshot-empty">
      {{ $t('step3.snapshotEmpty') }}
    </div>

    <!-- Bottom Info / Logs — T2 重构：分类 + 折叠 -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SIMULATION MONITOR</span>
        <span class="log-id">{{ simulationId || 'NO_SIMULATION' }}</span>
        <button v-if="hiddenCount > 0" class="log-toggle-btn" @click="showHidden = !showHidden">
          {{ showHidden ? '▾ 隐藏静态信息' : `▸ 显示 ${hiddenCount} 条静态信息` }}
        </button>
      </div>
      <div class="log-content" ref="logContent">
        <div
          v-for="(log, idx) in visibleLogs"
          :key="idx"
          class="log-line"
          :class="['log-line--' + log.category]"
        >
          <span class="log-icon">{{ log.icon }}</span>
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, shallowRef } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  startSimulation,
  stopSimulation,
  getRunStatus,
  getRunStatusDetail,
  createSnapshot,
  listSnapshots,
  restoreSnapshot,
  deleteSnapshot,
  getSimulationConfig
} from '../api/simulation'
import { generateReport } from '../api/report'

const route = useRoute()

const { t } = useI18n()

const props = defineProps({
  simulationId: String,
  maxRounds: Number, // 从Step2传入的最大轮数
  minutesPerRound: {
    type: Number,
    default: 30 // 默认每轮30分钟
  },
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

const router = useRouter()

// State
const isGeneratingReport = ref(false)
const phase = ref(0) // 0: 未开始, 1: 运行中, 2: 已完成
const isStarting = ref(false)
const isStopping = ref(false)
const startError = ref(null)
const runStatus = ref({})
// 错误监控：连续失败 N 次触发可见提示（后端静默报错的兜底）
const pollErrorCount = ref(0)
const pollErrorBanner = ref('')  // 非空时显示横幅
const allActions = ref([]) // 所有动作（增量累积）
const actionIds = shallowRef(new Set()) // 用于去重的动作ID集合（shallowRef 保证 Set 响应式）
// 方案 B：每个 round 都单独打印一条日志 —— 记录已发过日志的 round（按平台分别追踪）
// 修复 r0→r7 跳号：之前只在 current_round 跳变时打一条，OASIS 单轮快完成时一次轮询覆盖多轮，会丢中间 round 日志
const emittedTwitterRounds = new Set()
const emittedRedditRounds = new Set()
const scrollContainer = ref(null)

// 快照相关状态
const showSnapshotPanel = ref(false)
const snapshots = ref([])
const isCreatingSnapshot = ref(false)
const isRestoringSnapshot = ref(false)
const isDeletingSnapshot = ref(false)
const snapshotName = ref('') // 用户输入的快照名称
const showRestoreChoice = ref(false)
const restoreMode = ref('continue')
const selectedSnapshot = ref(null)
const restoreStartRound = ref(null) // 恢复快照时指定的 start_round
const wasRestored = ref(false) // 标记是否刚从快照恢复
const showAutoRestorePrompt = ref(false) // 自动检测到的可恢复快照提示
let autoRestoreTimer = null // 30s 兜底计时器（用户通过任何路径恢复/启动后必须取消）

// 收起自动恢复提示并取消 30s 兜底计时器
// 修复（恢复后计时器仍触发）：用户可能不点提示按钮，而是直接通过快照面板
// 恢复并启动了模拟——此时提示若不收起、计时器若不取消，30s 后会误弹轮数选择
const dismissAutoRestorePrompt = () => {
  showAutoRestorePrompt.value = false
  if (autoRestoreTimer) {
    clearTimeout(autoRestoreTimer)
    autoRestoreTimer = null
  }
}
const latestSnapshotForRestore = ref(null) // 自动检测到的最新快照
// 直接进入 Step3（历史入口 / Step4 回退 / Step5 重启）全新启动时的轮数选择
const showRoundsPrompt = ref(false) // 轮数选择提示
const roundsConfigLoading = ref(false) // 推荐轮数加载中
const promptAutoRounds = ref(null) // 配置自动计算的推荐轮数
const promptRounds = ref(40) // 用户输入的轮数（默认 40，与 Step2 推荐一致）
const pendingMaxRounds = ref(null) // 弹窗确认后待生效的轮数
const roundsPromptDismissed = ref(false) // 用户取消轮数选择后，保留重新打开入口

// Computed
// 按时间顺序显示动作（最新的在最后面，即底部）
// 修复（快照恢复后时间轴降序）：后端 get_all_actions 按时间戳降序返回，
// 恢复后的首轮轮询会把全部历史动作一次性按"最新在前"的顺序插入，
// 直接按插入顺序渲染会让时间轴卡片 R9 在顶、R1 在底。
// 统一按（轮次, 时间戳, 插入顺序）升序排列，与实时模拟"最新在底部"一致。
const chronologicalActions = computed(() => {
  return allActions.value
    .map((a, idx) => ({ a, idx }))
    .sort((x, y) => {
      const ra = x.a.round_num ?? 0
      const rb = y.a.round_num ?? 0
      if (ra !== rb) return ra - rb
      const ta = x.a.timestamp || ''
      const tb = y.a.timestamp || ''
      if (ta !== tb) return ta < tb ? -1 : 1
      return x.idx - y.idx
    })
    .map(({ a }) => a)
})

// 各平台动作计数
const twitterActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'twitter').length
})

const redditActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'reddit').length
})

// 格式化模拟流逝时间（根据轮次和每轮分钟数计算）
const formatElapsedTime = (currentRound) => {
  if (!currentRound || currentRound <= 0) return '0h 0m'
  const totalMinutes = currentRound * props.minutesPerRound
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${minutes}m`
}

// Twitter平台的模拟流逝时间
const twitterElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.twitter_current_round || 0)
})

// Reddit平台的模拟流逝时间
const redditElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.reddit_current_round || 0)
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// 重置所有状态（用于重新启动模拟）
// preserveRestore 为 true 时保留快照恢复相关的状态（wasRestored / restoreStartRound）
const resetAllState = (preserveRestore = false) => {
  phase.value = 0  // 0: 未开始, 1: 运行中, 2: 已完成
  runStatus.value = {}
  allActions.value = []
  actionIds.value = new Set()
  // 方案 B：重置时同时清空已发日志的 round 集合，避免重启模拟后旧 round 被跳过
  emittedTwitterRounds.clear()
  emittedRedditRounds.clear()
  prevTwitterRound.value = 0
  prevRedditRound.value = 0
  prevTwitterActions.value = 0
  prevRedditActions.value = 0
  twitterRoundDelta.value = 0
  redditRoundDelta.value = 0
  startError.value = null
  isStarting.value = false
  isStopping.value = false
  // 重置完成状态标志
  emit('update-status', 'processing')  // 重置为 processing 状态
  if (!preserveRestore) {
    restoreStartRound.value = null
    wasRestored.value = false
  }
  stopPolling()  // 停止之前可能存在的轮询
}

// 启动模拟
const doStartSimulation = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  // 快照恢复场景下：不清除恢复相关状态，但要清空前端展示数据
  const isFromRestore = wasRestored.value
  // 先重置所有状态，确保不会受到上一次模拟的影响
  resetAllState(isFromRestore)

  isStarting.value = true
  startError.value = null
  addLog(t('log.startingDualSim'))
  emit('update-status', 'processing')

  let simulationStarted = false  // 标记模拟是否成功启动

  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      enable_graph_memory_update: true  // 开启动态图谱更新
    }

    // force 策略：
    // - 快照恢复（无论继续/从头开始）：不传 force，保留恢复的文件
    //   OASIS 脚本会自动删除已存在的 DB 文件并重新创建
    // - 非快照恢复：传 force=true，强制清除旧状态
    if (!isFromRestore) {
      params.force = true
    }

    // 如果从快照恢复并选择了继续模式，传递 start_round
    if (restoreStartRound.value !== null && restoreStartRound.value > 0) {
      params.start_round = restoreStartRound.value
      addLog(`  └─ 使用快照恢复的 start_round: ${restoreStartRound.value}`)
      restoreStartRound.value = null  // 消费后清除
    } else {
      addLog(`  └─ start_round 未设置或为 0，将从头开始`)
    }

    // 仅非快照恢复模式传 max_rounds
    // 快照恢复后 total_rounds 已由快照恢复，不应再被 max_rounds 截断
    if (!isFromRestore) {
      // 优先用 Step2 传入的轮数；其次用直接进入时弹窗选择的轮数
      const rounds = props.maxRounds || pendingMaxRounds.value
      if (rounds) {
        params.max_rounds = rounds
        addLog(t('log.setMaxRounds', { rounds }))
      }
    }

    addLog(t('log.graphMemoryUpdateEnabled'))

    const res = await startSimulation(params)

    if (res.success && res.data) {
      if (res.data.force_restarted) {
        addLog(t('log.oldSimCleared'))
      }
      addLog(t('log.engineStarted'))
      addLog(`  ├─ PID: ${res.data.process_pid || '-'}`)
      addLog(`  ├─ total_rounds: ${res.data.total_rounds || 'null'}`)
      addLog(`  ├─ current_round: ${res.data.current_round || 0}`)

      phase.value = 1
      runStatus.value = res.data

      startStatusPolling()
      startDetailPolling()

      simulationStarted = true

      // 只有模拟成功启动后才清除恢复标记
      if (isFromRestore) {
        wasRestored.value = false
      }
    } else {
      startError.value = res.error || '启动失败'
      addLog(t('log.startFailed', { error: res.error || t('common.unknownError') }))
      emit('update-status', 'error')
    }
  } catch (err) {
    startError.value = err.message
    addLog(t('log.startException', { error: err.message }))
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
    // 如果模拟启动失败，恢复 wasRestored 标记，允许用户重试
    if (!simulationStarted && isFromRestore) {
      wasRestored.value = true
    }
  }
}

// 停止模拟
const handleStopSimulation = async () => {
  if (!props.simulationId) return
  
  isStopping.value = true
  addLog(t('log.stoppingSim'))
  
  try {
    const res = await stopSimulation({ simulation_id: props.simulationId })
    
    if (res.success) {
      addLog(t('log.simStoppedSuccess'))
      phase.value = 2
      stopPolling()
      emit('update-status', 'completed')
    } else {
      addLog(t('log.stopFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.stopException', { error: err.message }))
  } finally {
    isStopping.value = false
  }
}

// 轮询状态
let statusTimer = null
let detailTimer = null

// 动态轮询：接近完成时加速
const getDynamicInterval = () => {
  if (!runStatus.value || !runStatus.value.current_round || !runStatus.value.total_rounds) {
    return 2000
  }
  const current = runStatus.value.current_round
  const total = runStatus.value.total_rounds

  // 最后 5 轮加速到 1 秒
  if (total - current <= 5 && current > 0) {
    return 1000
  }
  // 最后 15 轮加速到 1.5 秒
  if (total - current <= 15 && current > 0) {
    return 1500
  }
  // 默认 2 秒
  return 2000
}

const startStatusPolling = () => {
  // 使用递归 setTimeout 实现动态间隔
  const poll = () => {
    fetchRunStatus().then((completed) => {
      if (!completed) {
        const interval = getDynamicInterval()
        statusTimer = setTimeout(poll, interval)
      }
    })
  }
  poll()
}

const startDetailPolling = () => {
  detailTimer = setInterval(fetchRunStatusDetail, 3000)
}

const stopPolling = () => {
  if (statusTimer) {
    clearTimeout(statusTimer)
    statusTimer = null
  }
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
}

// 追踪各平台的上一次轮次，用于检测变化并输出日志
const prevTwitterRound = ref(0)
const prevRedditRound = ref(0)
// T1：本轮活跃度增量（每轮变更时更新）
const prevTwitterActions = ref(0)
const prevRedditActions = ref(0)
const twitterRoundDelta = ref(0)
const redditRoundDelta = ref(0)

// T2：日志分类与折叠
const showHidden = ref(false)
const categorizedLogs = computed(() => {
  const logs = props.systemLogs || []
  return logs.map((log) => {
    const msg = log.msg || ''
    let category = 'info'
    let icon = '·'
    if (msg.includes('失败') || msg.toLowerCase().includes('error') || msg.includes('❌')) {
      category = 'error'; icon = '⚠'
    } else if (msg.startsWith('[✅ R') || msg.includes(' 完成 ')) {
      category = 'round'; icon = '✅'
    } else if (msg.includes('[Detail-Poll]')) {
      // 调试日志已在前面迁移到 console.debug，正常情况不会出现
      category = 'debug'; icon = '·'
    } else if (
      msg.includes('启动') || msg.includes('初始化') || msg.includes('设置') ||
      msg.includes('加载') || msg.includes('配置') || msg.includes('清理') ||
      msg.includes('自定义模拟') || msg.includes('开启动态') || msg.includes('已启动') ||
      msg.includes('✅ 模拟引擎') || msg.includes('✓ 已清理') || msg.includes('PID:')
    ) {
      category = 'config'; icon = '⚙'
    } else if (msg.includes('└─') || msg.includes('├─')) {
      category = 'config'; icon = ' '
    }
    return { ...log, category, icon }
  })
})
const visibleLogs = computed(() => {
  if (showHidden.value) return categorizedLogs.value
  return categorizedLogs.value.filter((l) => l.category !== 'config' && l.category !== 'debug')
})
const hiddenCount = computed(() =>
  categorizedLogs.value.filter((l) => l.category === 'config' || l.category === 'debug').length
)

const fetchRunStatus = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatus(props.simulationId)
    
    if (res.success && res.data) {
      const data = res.data
      
      runStatus.value = data

      // T4：轮次合并日志 —— 把双平台的轮次变更合并为单条结构化日志
      // 业务不变：仅 UI 聚合；后端数据来源不变
      const twChanged = data.twitter_current_round > prevTwitterRound.value
      const rdChanged = data.reddit_current_round > prevRedditRound.value
      if (twChanged && rdChanged) {
        addLog(`[✅ R${data.current_round}/${data.total_rounds}] Plaza A:${data.twitter_actions_count} | Community A:${data.reddit_actions_count} | T:${data.simulated_hours || 0}h`)
        twitterRoundDelta.value = Math.max(0, data.twitter_actions_count - prevTwitterActions.value)
        redditRoundDelta.value = Math.max(0, data.reddit_actions_count - prevRedditActions.value)
        prevTwitterActions.value = data.twitter_actions_count
        prevRedditActions.value = data.reddit_actions_count
        prevTwitterRound.value = data.twitter_current_round
        prevRedditRound.value = data.reddit_current_round
      } else if (twChanged) {
        addLog(`[✅ R${data.twitter_current_round}/${data.total_rounds}] Plaza A:${data.twitter_actions_count} | T:${data.twitter_simulated_hours || 0}h`)
        twitterRoundDelta.value = Math.max(0, data.twitter_actions_count - prevTwitterActions.value)
        prevTwitterActions.value = data.twitter_actions_count
        prevTwitterRound.value = data.twitter_current_round
      } else if (rdChanged) {
        addLog(`[✅ R${data.reddit_current_round}/${data.total_rounds}] Community A:${data.reddit_actions_count} | T:${data.reddit_simulated_hours || 0}h`)
        redditRoundDelta.value = Math.max(0, data.reddit_actions_count - prevRedditActions.value)
        prevRedditActions.value = data.reddit_actions_count
        prevRedditRound.value = data.reddit_current_round
      }
      
      // 检测模拟是否已完成/失败/停止（通过 runner_status 或平台完成状态判断）
      const isCompleted = data.runner_status === 'completed' || data.runner_status === 'stopped' || data.runner_status === 'failed'
      
      // 额外检查：如果后端还没来得及更新 runner_status，但平台已经报告完成
      // 通过检测 twitter_completed 和 reddit_completed 状态判断
      const platformsCompleted = checkPlatformsCompleted(data)
      
      if (isCompleted || platformsCompleted) {
        if (platformsCompleted && !isCompleted) {
          addLog(t('log.allPlatformsCompleted'))
        }
        if (data.runner_status === 'failed') {
          addLog(t('log.simFailed', { error: data.error || 'Unknown error' }))
          emit('update-status', 'failed')
          // 失败时自动创建快照
          await autoCreateSnapshotOnFail(data)
        } else {
          addLog(t('log.simCompleted'))
          emit('update-status', 'completed')
          // 成功完成时自动创建最终快照
          await autoCreateSnapshotOnComplete(data)
        }
        phase.value = 2
        stopPolling()
        return true  // 通知 poll 链不再继续
      }

      return false  // 模拟未完成，继续轮询
    } else if (res?.success) {
      // 成功但 data 缺失：重置错误计数 + 横幅
      if (pollErrorCount.value > 0) {
        pollErrorBanner.value = ''
        pollErrorCount.value = 0
      }
    }
  } catch (err) {
    console.warn('获取运行状态失败:', err)
    pollErrorCount.value++
    if (pollErrorCount.value >= 3 && !pollErrorBanner.value) {
      pollErrorBanner.value = `后端持续无响应（${pollErrorCount.value} 次）— 模拟可能已异常退出。请检查后端日志或刷新页面。`
      addLog(`[⚠️ 后端异常] 连续 ${pollErrorCount.value} 次轮询失败`)
    }
  }
  return false
}

// 检查所有启用的平台是否已完成
const checkPlatformsCompleted = (data) => {
  // 如果没有任何平台数据，返回 false
  if (!data) return false
  
  // 检查各平台的完成状态
  const twitterCompleted = data.twitter_completed === true
  const redditCompleted = data.reddit_completed === true
  
  // 如果至少有一个平台完成了，检查是否所有启用的平台都完成了
  // 通过 actions_count 判断平台是否被启用（如果 count > 0 或 running 曾为 true）
  const twitterEnabled = (data.twitter_actions_count > 0) || data.twitter_running || twitterCompleted
  const redditEnabled = (data.reddit_actions_count > 0) || data.reddit_running || redditCompleted
  
  // 如果没有任何平台被启用，返回 false
  if (!twitterEnabled && !redditEnabled) return false
  
  // 检查所有启用的平台是否都已完成
  if (twitterEnabled && !twitterCompleted) return false
  if (redditEnabled && !redditCompleted) return false
  
  return true
}

const fetchRunStatusDetail = async () => {
  if (!props.simulationId) return

  // 稳态调试信息：不再刷屏进 UI 面板，改走 console（F12 才能看到）
  // 业务行为完全不变：仍每 3s 轮询，仍增量拉取，仍新增动作去重
  console.debug(`[Detail-Poll] tick @ ${new Date().toLocaleTimeString()}`)
  try {
    const res = await getRunStatusDetail(props.simulationId)
    console.debug(`[Detail-Poll] success=${res?.success} all_actions=${(res?.data?.all_actions || []).length} idsSet=${actionIds.value.size} allActions=${allActions.value.length}`)
    if (res.success && res.data) {
      // 使用 all_actions 获取完整的动作列表
      const serverActions = res.data.all_actions || []

      // 修复（重放日志"累计"恒为总数）：快照恢复后的首轮轮询会一次性加入全部
      // 历史动作，若日志统一在循环后取 twitterActionsCount，每轮显示的都是
      // 最终总数。先记录本次加入前的基准值，逐轮累加还原真实累计进度。
      const twitterBase = twitterActionsCount.value
      const redditBase = redditActionsCount.value

      // 增量添加新动作（去重）
      let newActionsAdded = 0
      let firstNewAction = null
      // 方案 B：扫描本次新增动作里出现的 round_num，按平台分别累计，轮询结束后按 round 升序逐条打日志
      // 即使一次轮询覆盖了 r0..r7 共 8 轮，也会按顺序打 8 行，不会跳号
      const twitterRoundCounts = new Map() // round_num → 本次新增的 twitter 动作数
      const redditRoundCounts = new Map()
      serverActions.forEach(action => {
        // 生成唯一ID
        const actionId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}`

        if (!actionIds.value.has(actionId)) {
          actionIds.value.add(actionId)
          allActions.value.push({
            ...action,
            _uniqueId: actionId
          })
          newActionsAdded++
          if (!firstNewAction) firstNewAction = `R${action.round_num} ${action.platform}/${action.action_type}/${action.agent_name}`

          // 累计每个 round 的新增动作数（用于逐 round 日志）
          const r = action.round_num || 0
          if (r > 0) {
            const m = action.platform === 'twitter' ? twitterRoundCounts : (action.platform === 'reddit' ? redditRoundCounts : null)
            if (m) m.set(r, (m.get(r) || 0) + 1)
          }
        }
      })
      // 仅在真的有新动作时才往 UI 面板打一行（其它时候完全静默）
      if (newActionsAdded > 0) {
        addLog(`[Detail-Poll] +${newActionsAdded} new | first: ${firstNewAction}`)
      }

      // 方案 B：每个 round 都单独打印一行日志（按 round 升序，避免 r0→r7 跳号）
      // 同一轮不会被重复打印（用 emitted* Sets 去重）
      if (twitterRoundCounts.size > 0) {
        const rounds = [...twitterRoundCounts.keys()].sort((a, b) => a - b)
        let twitterCum = twitterBase
        for (const r of rounds) {
          twitterCum += twitterRoundCounts.get(r)
          if (emittedTwitterRounds.has(r)) continue
          emittedTwitterRounds.add(r)
          addLog(`[✅ R${r}] Plaza +${twitterRoundCounts.get(r)} actions (累计 ${twitterCum})`)
        }
      }
      if (redditRoundCounts.size > 0) {
        const rounds = [...redditRoundCounts.keys()].sort((a, b) => a - b)
        let redditCum = redditBase
        for (const r of rounds) {
          redditCum += redditRoundCounts.get(r)
          if (emittedRedditRounds.has(r)) continue
          emittedRedditRounds.add(r)
          addLog(`[✅ R${r}] Community +${redditRoundCounts.get(r)} actions (累计 ${redditCum})`)
        }
      }

      // 不自动滚动，让用户自由查看时间轴
      // 新动作会在底部追加
    }
  } catch (err) {
    console.warn('获取详细状态失败:', err)
    // detail-poll 失败不计入主错误计数器（detail 是次要数据）
    // 但若 detail 也持续失败 ≥ 6 次（≈30s），也提示用户
    if (pollErrorCount.value >= 6) {
      addLog(`[⚠️ Detail-Poll 持续失败] ${pollErrorCount.value} 次`)
    }
  }
}

// Helpers
// 已有专属卡片模板的动作类型（其余类型走通用回退，保证卡片永不空白）
const knownActionTypes = [
  'CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'CREATE_COMMENT',
  'SEARCH_POSTS', 'FOLLOW', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DISLIKE_POST',
  'LIKE_COMMENT', 'DISLIKE_COMMENT', 'MUTE', 'SEARCH_USER', 'TREND', 'DO_NOTHING',
]

// 判断专属模板是否会渲染出空卡片
// 后端 _enrich_action_context 查库失败时静默跳过（原帖被删/info_json 解析失败等），
// 字段会缺失。以下类型的模板内容全部是 v-if，字段缺失时卡片正文空白：
//   CREATE_POST: 依赖 content；QUOTE_POST: 依赖 quote_content/original_content；
//   CREATE_COMMENT: 依赖 content 或 post_id
// 其余类型（REPOST/FOLLOW/投票/搜索等）至少有一条常显 info 行，永不空白
const isCardBodyEmpty = (action) => {
  const args = action.action_args || {}
  switch (action.action_type) {
    case 'CREATE_POST':
      return !args.content
    case 'QUOTE_POST':
      return !args.quote_content && !args.original_content
    case 'CREATE_COMMENT':
      return !args.content && !args.post_id
    default:
      return false
  }
}

const getActionTypeLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST',
    'REPOST': 'REPOST',
    'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT',
    'LIKE_COMMENT': 'LIKE',
    'DO_NOTHING': 'IDLE',
    'FOLLOW': 'FOLLOW',
    'SEARCH_POSTS': 'SEARCH',
    'SEARCH_USER': 'SEARCH',
    'TREND': 'TREND',
    'MUTE': 'MUTE',
    'QUOTE_POST': 'QUOTE',
    'UPVOTE_POST': 'UPVOTE',
    'DOWNVOTE_POST': 'DOWNVOTE',
    'DISLIKE_POST': 'DISLIKE',
    'DISLIKE_COMMENT': 'DISLIKE'
  }
  return labels[type] || type || 'UNKNOWN'
}

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post',
    'REPOST': 'badge-action',
    'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment',
    'LIKE_COMMENT': 'badge-action',
    'DISLIKE_COMMENT': 'badge-action',
    'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta',
    'SEARCH_POSTS': 'badge-meta',
    'SEARCH_USER': 'badge-meta',
    'TREND': 'badge-meta',
    'MUTE': 'badge-meta',
    'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action',
    'DISLIKE_POST': 'badge-action',
    'DO_NOTHING': 'badge-idle'
  }
  return classes[type] || 'badge-default'
}

const truncateContent = (content, maxLength = 100) => {
  if (!content) return ''
  if (content.length > maxLength) return content.substring(0, maxLength) + '...'
  return content
}

const formatActionTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

const handleNextStep = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  if (isGeneratingReport.value) {
    addLog(t('log.reportRequestSent'))
    return
  }

  isGeneratingReport.value = true
  addLog(t('log.startingReportGen'))

  // 优化 R2/R4：智能判断 force_regenerate
  // 1. 先查报告状态（无报告 / completed / generating / failed）
  // 2. 默认进入恢复模式（不传 force_regenerate），让后端 R1+R2 自动跳过已有章节
  // 3. 只有用户显式点"强制重新生成"才传 force_regenerate=true
  try {
    const { checkReportStatus } = await import('../api/report')
    const checkRes = await checkReportStatus(props.simulationId)

    let params = { simulation_id: props.simulationId }

    if (checkRes.success && checkRes.data) {
      const status = checkRes.data.report_status
      const resumable = checkRes.data.resumable
      const completed = checkRes.data.completed_sections || 0
      const total = checkRes.data.total_sections || 0

      if (status === 'completed') {
        // 已完成 → 直接跳转到 Report 页（后端会返回 already_generated）
        addLog(`报告已存在 (${checkRes.data.report_id})，直接进入查看`)
      } else if (status === 'generating') {
        // 正在生成中 → 直接跳转，让用户看到进度
        addLog(`报告正在生成中，进入查看页面`)
      } else if (status === 'failed' && resumable) {
        // 失败且可恢复 → 默认走恢复模式（不传 force_regenerate），R1 会跳过已有章节
        addLog(`检测到失败报告，已生成 ${completed}/${total} 章节，进入恢复模式`)
      }
      // 其他情况（无报告 / pending / planning）走默认 params（不传 force_regenerate）
    }

    const res = await generateReport(params)

    if (res.success && res.data) {
      const reportId = res.data.report_id
      addLog(t('log.reportGenTaskStarted', { reportId }))

      // 跳转到报告页面
      router.push({ name: 'Report', params: { reportId } })
    } else {
      addLog(t('log.reportGenFailed', { error: res.error || t('common.unknownError') }))
      isGeneratingReport.value = false
    }
  } catch (err) {
    addLog(t('log.reportGenException', { error: err.message }))
    isGeneratingReport.value = false
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

onMounted(() => {
  addLog(t('log.step3Init'))
  if (props.simulationId) {
    // 检测入口：是否从 Step5 重启过来
    // ?from=step5_restart 表示用户主动重启，跳过"恢复快照"提示
    // （因为 force=true 会清掉旧状态，恢复快照是反向操作）
    const fromStep5Restart = route.query.from === 'step5_restart'

    if (!fromStep5Restart) {
      // 普通入口（首次进入 / 从 Step4 回退）：
      // 防护（force=true 误清理快照）：
      // 之前 doStartSimulation() 立即 fire  force=true 会清空 actions.jsonl 和 run_state.json，
      // 把所有历史的 R0~Rn actions 抹掉，导致前面 OASIS 跑的成果丢失。
      // 修复：先 checkAndPromptRestoreSnapshotAsync() 等待用户选择；
      //   - 如果用户选"恢复快照"：doRestoreStart() 用 start_round=N 不带 force=true 启动
      //   - 如果用户选"force 全新启动"或没有 snapshot：才走原 force=true 路径
      checkAndPromptRestoreSnapshotAsync()
    } else {
      addLog(t('log.step3RestartFromStep5'))
      // 重启也是全新 force 启动，同样先让用户确认本次模拟轮数
      openRoundsPrompt()
    }
  }
})

onUnmounted(() => {
  stopPolling()
  // 清理自动恢复提示的 30s 兜底计时器，避免组件销毁后仍触发 openRoundsPrompt
  if (autoRestoreTimer) {
    clearTimeout(autoRestoreTimer)
    autoRestoreTimer = null
  }
})

// ==================== 快照相关方法 ====================

// 失败时自动创建快照
const autoCreateSnapshotOnFail = async (failData) => {
  if (!props.simulationId) return

  const currentRound = failData.current_round || 0
  const totalRound = failData.total_rounds || '?'
  const name = `fail_R${currentRound}_${totalRound}`

  addLog(t('log.autoSnapshotCreating', { round: currentRound, total: totalRound }))

  try {
    const res = await createSnapshot(props.simulationId, { snapshot_name: name })
    if (res.success) {
      addLog(t('log.autoSnapshotCreated', { name: res.data.snapshot_name }))
    } else {
      addLog(t('log.autoSnapshotFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.autoSnapshotException', { error: err.message }))
  }
}

// 成功完成时自动创建最终快照
const autoCreateSnapshotOnComplete = async (completeData) => {
  if (!props.simulationId) return

  const totalRound = completeData.total_rounds || '?'
  const name = `final_R${totalRound}`

  addLog(t('log.autoFinalSnapshotCreating', { round: totalRound }))

  try {
    const res = await createSnapshot(props.simulationId, { snapshot_name: name })
    if (res.success) {
      addLog(t('log.autoFinalSnapshotCreated', { name: res.data.snapshot_name }))
    } else {
      addLog(t('log.autoSnapshotFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.autoSnapshotException', { error: err.message }))
  }
}

// 创建快照
const handleCreateSnapshot = async () => {
  if (!props.simulationId) {
    addLog(t('log.snapshotNoSimId'))
    return
  }

  const name = snapshotName.value.trim() || undefined
  isCreatingSnapshot.value = true

  addLog(t('log.snapshotCreating', { name: name || t('log.snapshotAuto') }))

  try {
    const res = await createSnapshot(props.simulationId, { snapshot_name: name })

    if (res.success) {
      addLog(t('log.snapshotCreated', { name: res.data.snapshot_name }))
      snapshotName.value = ''
      // 刷新快照列表
      await handleListSnapshots()
    } else {
      addLog(t('log.snapshotCreateFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.snapshotCreateException', { error: err.message }))
  } finally {
    isCreatingSnapshot.value = false
  }
}

// 检测并提示恢复最后快照
// 当用户从第四章回退到第三章时，如果模拟已完成/失败且有快照，自动提示
const checkAndPromptRestoreSnapshot = async () => {
  if (!props.simulationId) return

  try {
    const res = await listSnapshots(props.simulationId)

    if (res.success && res.data?.snapshots?.length > 0) {
      // 按创建时间排序，取最新的快照
      const snapshots = [...res.data.snapshots].sort((a, b) => {
        const timeA = new Date(a.created_at || 0).getTime()
        const timeB = new Date(b.created_at || 0).getTime()
        return timeB - timeA
      })

      const latest = snapshots[0]

      // 判断这个最新快照是否是"有意义的"（不是空的）
      // 有意义的快照：final_ 前缀（成功完成）或 fail_ 前缀（失败）
      const isFinalSnapshot = latest.snapshot_name.startsWith('final_')
      const isFailSnapshot = latest.snapshot_name.startsWith('fail_')

      if (isFinalSnapshot || isFailSnapshot) {
        addLog(t('log.hasPreviousSnapshot', { name: latest.snapshot_name }))
        // 显示一个可点击的提示，让用户选择是否恢复
        showAutoRestorePrompt.value = true
        latestSnapshotForRestore.value = latest
      }
    }
  } catch (err) {
    console.warn('检测可恢复快照失败:', err)
  }
}

// 防护（force=true 误清理快照）：异步版本
// 检查快照是否存在有意义快照（final_/fail_）；如有，把选择交给用户：
//   - 选 "恢复快照"：调用 doRestoreStart(snapshot)，跳过 force=true
//   - 选 "force 全新启动"：调用 doStartSimulation() 走原 force=true 路径
//   - 30 秒无响应 / 没有 snapshot：自动 force=true
const checkAndPromptRestoreSnapshotAsync = async () => {
  if (!props.simulationId) {
    doStartSimulation()
    return
  }

  let hasMeaningfulSnapshot = false
  try {
    const res = await listSnapshots(props.simulationId)
    if (res.success && res.data?.snapshots?.length > 0) {
      const snapshots = [...res.data.snapshots].sort((a, b) => {
        const tA = new Date(a.created_at || 0).getTime()
        const tB = new Date(b.created_at || 0).getTime()
        return tB - tA
      })
      const latest = snapshots[0]
      const isFinal = latest.snapshot_name.startsWith('final_')
      const isFail = latest.snapshot_name.startsWith('fail_')
      if (isFinal || isFail) {
        hasMeaningfulSnapshot = true
        latestSnapshotForRestore.value = latest
        addLog(t('log.hasPreviousSnapshot', { name: latest.snapshot_name }))
        showAutoRestorePrompt.value = true
      }
    }
  } catch (err) {
    console.warn('检测快照失败:', err)
  }

  if (!hasMeaningfulSnapshot) {
    // 没有有意义快照：全新 force 启动前先让用户选择本次模拟的轮数
    openRoundsPrompt()
    return
  }

  // 有快照：等用户选择。showAutoRestorePrompt=true 后用户点 UI 按钮（详见模板）：
  //   - "从快照继续" → handleContinueAutoRestore → 恢复弹窗
  //   - "force 全新启动" → handleAutoRestoreDismiss → openRoundsPrompt（force=true）
  // 这里什么都不做，等 UI 回调。
  // 30 秒兜底：避免用户没看到提示，sim 卡死。
  // 兜底不再自动 force 启动（会误清快照），改为收起提示并进入轮数选择。
  // 双重防护：用户可能已通过快照面板恢复并启动了模拟（dismissAutoRestorePrompt
  // 会取消本计时器）；即使计时器未被取消（旧路径），模拟已运行时也不再弹轮数选择
  autoRestoreTimer = setTimeout(() => {
    autoRestoreTimer = null
    if (!showAutoRestorePrompt.value || isStarting.value) return
    showAutoRestorePrompt.value = false
    if (phase.value === 1 || runStatus.value.twitter_running || runStatus.value.reddit_running) {
      // 模拟已通过其他路径启动，无需再选轮数
      return
    }
    addLog('30秒未选择，进入轮数选择')
    openRoundsPrompt()
  }, 30000)
}

// 自动恢复取消（用户点 "force 全新启动" 按钮时调用）
const handleAutoRestoreDismiss = () => {
  dismissAutoRestorePrompt()
  openRoundsPrompt()
}

// ==================== 全新启动轮数选择 ====================

// 直接进入 Step3（历史入口 / Step4 回退 / Step5 重启）时的全新启动：
// 不再默默以默认轮数 force 启动，先弹出轮数选择，由用户确认本次模拟轮数
const openRoundsPrompt = async () => {
  // Step2 流程已带轮数（query 参数传入），无需再询问
  if (props.maxRounds) {
    doStartSimulation()
    return
  }

  showRoundsPrompt.value = true
  roundsPromptDismissed.value = false
  roundsConfigLoading.value = true
  try {
    // 获取模拟配置，计算推荐轮数（与 Step2 autoGeneratedRounds 同口径）
    const res = await getSimulationConfig(props.simulationId)
    if (res.success && res.data?.time_config) {
      const totalHours = res.data.time_config.total_simulation_hours
      const minutesPerRound = res.data.time_config.minutes_per_round
      if (totalHours && minutesPerRound) {
        const calculated = Math.max(Math.floor((totalHours * 60) / minutesPerRound), 40)
        promptAutoRounds.value = calculated
        promptRounds.value = calculated
        addLog(t('log.autoRoundsDetected', { rounds: calculated }))
      }
    }
  } catch (err) {
    console.warn('获取模拟配置失败:', err)
  } finally {
    roundsConfigLoading.value = false
  }
}

// 轮数选择确认：按用户输入的轮数全新启动
const handleRoundsPromptConfirm = () => {
  let rounds = parseInt(promptRounds.value, 10)
  if (!rounds || rounds < 10) {
    addLog(t('log.invalidRoundsInput'))
    return
  }
  // 超过推荐轮数时按推荐轮数截断（与 Step2 滑条上限一致）
  if (promptAutoRounds.value && rounds > promptAutoRounds.value) {
    addLog(t('log.roundsCapped', { auto: promptAutoRounds.value }))
    rounds = promptAutoRounds.value
  }

  pendingMaxRounds.value = rounds
  showRoundsPrompt.value = false
  doStartSimulation()
}

// 轮数选择取消：不启动模拟，收起提示但保留重新打开入口
const handleRoundsPromptCancel = () => {
  showRoundsPrompt.value = false
  roundsPromptDismissed.value = true
  addLog(t('log.roundsPromptCancelled'))
}

// 重新打开轮数选择（用户点了收起提示中的启动入口）
const reopenRoundsPrompt = () => {
  roundsPromptDismissed.value = false
  openRoundsPrompt()
}

// 快照时间解析（容错：解析失败返回 0，排最前）
const snapshotTime = (s) => {
  const t = Date.parse(s?.created_at)
  return Number.isNaN(t) ? 0 : t
}

// 列出快照
const handleListSnapshots = async () => {
  if (!props.simulationId) return

  try {
    const res = await listSnapshots(props.simulationId)

    if (res.success) {
      // 后端返回倒序（最新在前）；面板卡片按时间升序展示（最旧在前，符合时间线阅读习惯）
      snapshots.value = [...(res.data.snapshots || [])].sort(
        (a, b) => snapshotTime(a) - snapshotTime(b)
      )
      showSnapshotPanel.value = true
      // 关闭恢复选择对话框，避免显示不一致的状态
      showRestoreChoice.value = false
    }
  } catch (err) {
    console.error('获取快照列表失败:', err)
  }
}

// 恢复快照 — 弹出选择弹窗
const handleRestoreSnapshot = async (snapshot) => {
  if (!props.simulationId) return

  selectedSnapshot.value = snapshot
  restoreMode.value = 'continue'
  showRestoreChoice.value = true
}

// 从自动恢复提示中继续
const handleContinueAutoRestore = () => {
  if (!latestSnapshotForRestore.value) return
  selectedSnapshot.value = latestSnapshotForRestore.value
  restoreMode.value = 'continue'
  showRestoreChoice.value = true
  dismissAutoRestorePrompt()
}

// 忽略自动恢复提示
const handleIgnoreAutoRestore = () => {
  dismissAutoRestorePrompt()
  latestSnapshotForRestore.value = null
  // 不自动启动（避免 force 误清快照），但显示"开始模拟"入口避免死局
  roundsPromptDismissed.value = true
}

// 取消恢复操作
const handleCancelRestore = () => {
  showRestoreChoice.value = false
  selectedSnapshot.value = null
  restoreMode.value = 'continue'
}

// 双平台轮次描述：已完成的平台显示"已完成全部 N 轮"，未完成的显示各自下一轮。
// 避免 completed_round >= total_rounds 时仍显示"从第 N+1 轮开始"的越界误导
// （例：total=10、Plaza 完成 R10、Community 完成 R7 →
//   "Plaza 已完成全部 10 轮 / Community 从第 8 轮开始"）
const platformRoundsLabel = (twRound, rdRound, totalRounds) => {
  if (!Number.isInteger(totalRounds) || totalRounds <= 0) return null
  if (!Number.isInteger(twRound) || !Number.isInteger(rdRound)) return null
  const twDone = twRound >= totalRounds
  const rdDone = rdRound >= totalRounds
  if (twDone && rdDone) {
    return t('log.snapshotRestoreAllDone', { total: totalRounds })
  }
  if (twDone) {
    return t('log.snapshotRestoreTwDone', { total: totalRounds, reddit: rdRound + 1 })
  }
  if (rdDone) {
    return t('log.snapshotRestoreRdDone', { total: totalRounds, twitter: twRound + 1 })
  }
  return t('log.snapshotRestorePlatformRounds', { twitter: twRound + 1, reddit: rdRound + 1 })
}

// 快照"从快照继续"的轮次描述：优先用 runtime_rounds（子进程每轮落盘的真实进度），
// 旧快照无该字段时回退 run_state（monitor 落盘，可能滞后一轮）
const snapshotContinueLabel = (snapshot) => {
  const rs = snapshot?.run_state
  const rt = snapshot?.runtime_rounds
  const tw = rt?.twitter ?? rs?.twitter_current_round
  const rd = rt?.reddit ?? rs?.reddit_current_round
  const label = platformRoundsLabel(tw, rd, rs?.total_rounds)
  return label ?? t('log.snapshotRestoreContinueFromSnapshot', { round: rs?.current_round || 0 })
}

// 模拟运行中的切换前处理：先停止当前模拟，并把当前进度保存为快照
// 1. 必须先停：运行中的进程会持续写 actions.jsonl / run_state.json，
//    与恢复快照/全新启动存在文件竞争
// 2. 保存现场：force 全新启动会清空日志，恢复其他快照会覆盖当前状态，
//    先留一份 pre_restore 快照保证当前进度可回溯
const stopAndSnapshotCurrentRun = async () => {
  const isRunning = phase.value === 1 || runStatus.value.twitter_running || runStatus.value.reddit_running
  if (!isRunning) return

  // 1. 停止当前模拟进程
  addLog(t('log.stoppingSim'))
  const stopRes = await stopSimulation({ simulation_id: props.simulationId })
  if (!stopRes.success) {
    const msg = stopRes.error || ''
    // 后端报"未在运行"说明进程已停止，可继续；其他错误中止切换
    if (!(msg.includes('未在运行') || msg.toLowerCase().includes('not running'))) {
      throw new Error(msg || t('common.unknownError'))
    }
  }
  addLog(t('log.simStoppedSuccess'))
  stopPolling()
  phase.value = 0

  // 2. 保存当前进度快照（名称带轮次+时间戳，避免覆盖）
  const currentRound = runStatus.value.current_round || 0
  const ts = new Date().toISOString().slice(11, 19).replace(/:/g, '')
  const snapName = `pre_restore_R${currentRound}_${ts}`
  const snapRes = await createSnapshot(props.simulationId, { snapshot_name: snapName })
  if (snapRes.success) {
    addLog(t('log.preRestoreSnapshotCreated', { name: snapRes.data.snapshot_name }))
  } else {
    // 快照失败不阻断切换，仅提示当前进度无法回溯
    addLog(t('log.preRestoreSnapshotFailed', { error: snapRes.error || t('common.unknownError') }))
  }
}

// 执行恢复（从弹窗确认）
const doRestoreSnapshot = async () => {
  const snapshot = selectedSnapshot.value
  if (!snapshot || !props.simulationId) return

  showRestoreChoice.value = false
  isRestoringSnapshot.value = true

  // 用户没有点自动恢复提示的按钮，而是直接通过快照面板选择了恢复：
  // 收起提示并取消 30s 兜底计时器，避免恢复启动后再误弹轮数选择
  dismissAutoRestorePrompt()

  try {
    // 模拟运行中：先停止当前模拟并保存现场快照，再执行所选操作
    await stopAndSnapshotCurrentRun()

    // "从头开始"：无需恢复快照文件（恢复了也是带旧状态重跑，毫无意义）。
    // 直接走全新启动流程：先选轮数，再 force=true 清空旧状态、从第 0 轮重跑所有轮次
    if (restoreMode.value !== 'continue') {
      selectedSnapshot.value = null
      showSnapshotPanel.value = false
      addLog(t('log.snapshotStartOverDirect', { name: snapshot.snapshot_name }))
      openRoundsPrompt()
      return
    }

    // "从快照继续"：恢复快照文件，再以 start_round=N 启动（不带 force=true）
    addLog(t('log.snapshotRestoring', { name: snapshot.snapshot_name }))

    const res = await restoreSnapshot(props.simulationId, {
      snapshot_name: snapshot.snapshot_name,
    })

    if (res.success) {
      // 使用后端返回的 current_round，而不是本地计算的值
      const startRound = res.data.current_round || 0

      addLog(t('log.snapshotRestored', { name: res.data.snapshot_name }))
      // 双平台独立轮次：已完成的平台显示"已完成"，未完成的显示各自下一轮
      // （例：Plaza 完成 10/10 → "Plaza 已完成全部 10 轮"，而非"从第 11 轮开始"）
      const roundsLabel = platformRoundsLabel(
        res.data.twitter_round, res.data.reddit_round, res.data.total_rounds
      )
      if (roundsLabel) {
        addLog(roundsLabel)
      } else {
        addLog(t('log.snapshotRestoreContinueFromSnapshot', { round: startRound + 1 }))
      }

      // 设置恢复标记，阻止 doStartSimulation 误传 max_rounds
      wasRestored.value = true
      restoreStartRound.value = startRound > 0 ? startRound : null

      // 恢复文件后，调用 doStartSimulation 启动模拟进程
      // doStartSimulation 内部会先 resetAllState 清空前端数据，然后调用后端 start_simulation
      // 后端会使用恢复的 run_state.json 和 actions.jsonl 数据
      await doStartSimulation()
      showSnapshotPanel.value = false
    } else {
      addLog(t('log.snapshotRestoreFailed', { error: res.error || t('common.unknownError') }))
      wasRestored.value = false
    }
  } catch (err) {
    addLog(t('log.snapshotRestoreAborted', { error: err.message }))
    wasRestored.value = false
  } finally {
    isRestoringSnapshot.value = false
    selectedSnapshot.value = null
  }
}

// 删除快照
const handleDeleteSnapshot = async (snapshotName) => {
  if (!props.simulationId) return

  const confirmed = confirm(t('log.snapshotDeleteConfirm', { name: snapshotName }))
  if (!confirmed) return

  isDeletingSnapshot.value = true

  try {
    const res = await deleteSnapshot(props.simulationId, snapshotName)

    if (res.success) {
      addLog(t('log.snapshotDeleted', { name: snapshotName }))
      // 刷新快照列表
      await handleListSnapshots()
    } else {
      addLog(t('log.snapshotDeleteFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.snapshotDeleteException', { error: err.message }))
  } finally {
    isDeletingSnapshot.value = false
  }
}

</script>

<style scoped>
.simulation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  overflow: hidden;
}

/* --- Control Bar --- */
.control-bar {
  background: #FFF;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #EAEAEA;
  z-index: 10;
  min-height: 64px;
  flex-wrap: wrap;
  gap: 12px;
}

.status-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: stretch;
}

/* Platform Status Cards */
.platform-status {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 4px;
  background: #FAFAFA;
  border: 1px solid #EAEAEA;
  opacity: 0.7;
  transition: all 0.3s;
  min-width: 200px;
  position: relative;
  cursor: pointer;
}

.platform-status.active {
  opacity: 1;
  border-color: #333;
  background: #FFF;
}

.platform-status.completed {
  opacity: 1;
  border-color: #1A936F;
  background: #F2FAF6;
}

/* Actions Tooltip */
.actions-tooltip {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  padding: 10px 14px;
  background: #000;
  color: #FFF;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 100;
  min-width: 180px;
  pointer-events: none;
}

.actions-tooltip::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 6px solid #000;
}

.platform-status:hover .actions-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-title {
  font-size: 10px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.tooltip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tooltip-action {
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
  color: #FFF;
  letter-spacing: 0.03em;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.platform-name {
  font-size: 11px;
  font-weight: 700;
  color: #000;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.platform-status.twitter .platform-icon { color: #000; }
.platform-status.reddit .platform-icon { color: #000; }

.platform-stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: baseline;
}

/* T1：本轮增量 pill */
.round-delta-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 3px 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border-radius: 3px;
  width: fit-content;
  animation: roundDeltaFadeIn 0.4s ease-out;
}
.round-delta-pill.twitter {
  background: rgba(255, 107, 53, 0.12);
  color: #FF5722;
  border: 1px solid rgba(255, 87, 34, 0.35);
}
.round-delta-pill.reddit {
  background: rgba(0, 78, 137, 0.12);
  color: #004E89;
  border: 1px solid rgba(0, 78, 137, 0.35);
}
.round-delta-icon {
  font-size: 9px;
}
.round-delta-text {
  font-size: 10px;
}
@keyframes roundDeltaFadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to { opacity: 1; transform: translateY(0); }
}

.stat {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.stat-label {
  font-size: 8px;
  color: #999;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 11px;
  font-weight: 600;
  color: #333;
}

.stat-total, .stat-unit {
  font-size: 9px;
  color: #999;
  font-weight: 400;
}

.status-badge {
  margin-left: auto;
  color: #1A936F;
  display: flex;
  align-items: center;
}

/* Action Controls */
.action-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

/* 后端异常横幅 */
.poll-error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 24px;
  background: linear-gradient(180deg, rgba(255, 87, 34, 0.08), rgba(255, 87, 34, 0.04));
  border-bottom: 1px solid rgba(255, 87, 34, 0.25);
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #FF5722;
  animation: pollErrorFadeIn 0.3s ease-out;
}
.poll-error-banner .banner-icon {
  font-size: 14px;
}
.poll-error-banner .banner-text {
  flex: 1;
  font-weight: 600;
}
.poll-error-banner .banner-dismiss {
  background: transparent;
  border: 1px solid rgba(255, 87, 34, 0.4);
  color: #FF5722;
  width: 22px;
  height: 22px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.poll-error-banner .banner-dismiss:hover {
  background: rgba(255, 87, 34, 0.15);
  border-color: #FF5722;
}
@keyframes pollErrorFadeIn {
  from { opacity: 0; transform: translateY(-2px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Action Button */
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.action-btn.primary {
  background: #000;
  color: #FFF;
}

.action-btn.primary:hover:not(:disabled) {
  background: #333;
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* --- Main Content Area --- */
.main-content-area {
  flex: 1;
  overflow-y: auto;
  position: relative;
  background: #FFF;
}

/* Timeline Header */
.timeline-header {
  position: sticky;
  top: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  padding: 12px 24px;
  border-bottom: 1px solid #EAEAEA;
  z-index: 5;
  display: flex;
  justify-content: center;
}

.timeline-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 11px;
  color: #666;
  background: #F5F5F5;
  padding: 4px 12px;
  border-radius: 20px;
}

.total-count {
  font-weight: 600;
  color: #333;
}

.platform-breakdown {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.breakdown-divider { color: #DDD; }
.breakdown-item.twitter { color: #000; }
.breakdown-item.reddit { color: #000; }

/* --- Timeline Feed --- */
.timeline-feed {
  padding: 24px 0;
  position: relative;
  min-height: 100%;
  max-width: 900px;
  margin: 0 auto;
}

.timeline-axis {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #EAEAEA; /* Cleaner line */
  transform: translateX(-50%);
}

.timeline-item {
  display: flex;
  justify-content: center;
  margin-bottom: 32px;
  position: relative;
  width: 100%;
}

.timeline-marker {
  position: absolute;
  left: 50%;
  top: 24px;
  width: 10px;
  height: 10px;
  background: #FFF;
  border: 1px solid #CCC;
  border-radius: 50%;
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
}

.marker-dot {
  width: 4px;
  height: 4px;
  background: #CCC;
  border-radius: 50%;
}

.timeline-item.twitter .marker-dot { background: #000; }
.timeline-item.reddit .marker-dot { background: #000; }
.timeline-item.twitter .timeline-marker { border-color: #000; }
.timeline-item.reddit .timeline-marker { border-color: #000; }

/* Card Layout */
.timeline-card {
  width: calc(100% - 48px);
  background: #FFF;
  border-radius: 2px;
  padding: 16px 20px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  position: relative;
  transition: all 0.2s;
}

.timeline-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  border-color: #DDD;
}

/* Left side (Twitter) */
.timeline-item.twitter {
  justify-content: flex-start;
  padding-right: 50%;
}
.timeline-item.twitter .timeline-card {
  margin-left: auto;
  margin-right: 32px; /* Gap from axis */
}

/* Right side (Reddit) */
.timeline-item.reddit {
  justify-content: flex-end;
  padding-left: 50%;
}
.timeline-item.reddit .timeline-card {
  margin-right: auto;
  margin-left: 32px; /* Gap from axis */
}

/* Card Content Styles */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #F5F5F5;
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar-placeholder {
  width: 24px;
  height: 24px;
  background: #000;
  color: #FFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: #000;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-indicator {
  color: #999;
  display: flex;
  align-items: center;
}

.action-badge {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 2px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid transparent;
}

/* Monochromatic Badges */
.badge-post { background: #F0F0F0; color: #333; border-color: #E0E0E0; }
.badge-comment { background: #F0F0F0; color: #666; border-color: #E0E0E0; }
.badge-action { background: #FFF; color: #666; border: 1px solid #E0E0E0; }
.badge-meta { background: #FAFAFA; color: #999; border: 1px dashed #DDD; }
.badge-idle { opacity: 0.5; }

.content-text {
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  margin-bottom: 10px;
}

.content-text.main-text {
  font-size: 14px;
  color: #000;
}

/* Info Blocks (Quote, Repost, etc) */
.quoted-block, .repost-content {
  background: #F9F9F9;
  border: 1px solid #EEE;
  padding: 10px 12px;
  border-radius: 2px;
  margin-top: 8px;
  font-size: 12px;
  color: #555;
}

.quote-header, .repost-info, .like-info, .search-info, .follow-info, .vote-info, .idle-info, .comment-context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 11px;
  color: #666;
}

.icon-small {
  color: #999;
}
.icon-small.filled {
  color: #999; /* Keep icons neutral unless highlighted */
}

.search-query {
  font-family: 'JetBrains Mono', monospace;
  background: #F0F0F0;
  padding: 0 4px;
  border-radius: 2px;
}

.card-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  font-size: 10px;
  color: #BBB;
  font-family: 'JetBrains Mono', monospace;
}

/* Waiting State */
.waiting-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #CCC;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.pulse-ring {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #EAEAEA;
  animation: ripple 2s infinite;
}

@keyframes ripple {
  0% { transform: scale(0.8); opacity: 1; border-color: #CCC; }
  100% { transform: scale(2.5); opacity: 0; border-color: #EAEAEA; }
}

/* Animation */
.timeline-item-enter-active,
.timeline-item-leave-active {
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.timeline-item-leave-to {
  opacity: 0;
}

/* Logs */
.system-logs {
  background: #000;
  color: #DDD;
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #222;
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #333;
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: #666;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time { color: #555; min-width: 75px; }
.log-msg { color: #BBB; word-break: break-all; }

/* T2：日志分类 */
.log-icon {
  display: inline-block;
  min-width: 14px;
  font-size: 10px;
  text-align: center;
}
.log-line--round .log-icon { color: #1A936F; }
.log-line--round .log-msg { color: #DDD; font-weight: 500; }
.log-line--config .log-time { color: #444; }
.log-line--config .log-msg { color: #888; }
.log-line--error .log-icon { color: #FF5722; }
.log-line--error .log-time { color: #FF5722; }
.log-line--error .log-msg { color: #FFAB91; }
.log-toggle-btn {
  margin-left: auto;
  padding: 2px 8px;
  background: transparent;
  border: 1px solid #444;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s ease;
}
.log-toggle-btn:hover {
  color: #FFF;
  border-color: #888;
}
.mono { font-family: 'JetBrains Mono', monospace; }

/* Loading spinner for button */
.loading-spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #FFF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
}

/* ==================== 快照管理面板样式 ==================== */
.snapshot-panel {
  background: #F8F9FA;
  border-top: 1px solid #E0E0E0;
  padding: 16px 24px;
  max-height: 300px;
  overflow-y: auto;
}

.snapshot-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #DDD;
}

.snapshot-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.snapshot-close-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}

.snapshot-close-btn:hover {
  color: #333;
}

.snapshot-create-section {
  margin-bottom: 12px;
}

.create-form {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.snapshot-name-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #DDD;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  background: #FFF;
}

.snapshot-name-input:focus {
  outline: none;
  border-color: #000;
}

.create-snapshot-btn {
  padding: 8px 16px;
  background: #000;
  color: #FFF;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}

.create-snapshot-btn:hover:not(:disabled) {
  background: #333;
}

.create-snapshot-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.create-hint {
  font-size: 11px;
  color: #888;
  margin: 0;
}

.snapshot-list-section {
  margin-top: 12px;
}

.snapshot-list-header {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.snapshot-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #FFF;
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  transition: all 0.2s;
}

.snapshot-item:hover {
  border-color: #CCC;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.snapshot-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.snapshot-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  font-family: 'JetBrains Mono', monospace;
}

.snapshot-time {
  font-size: 11px;
  color: #888;
}

.snapshot-stats {
  display: flex;
  gap: 6px;
}

.stat-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: #F0F0F0;
  color: #666;
  border-radius: 2px;
  font-weight: 500;
}

.snapshot-actions {
  display: flex;
  gap: 4px;
}

.snapshot-action-btn {
  background: none;
  border: 1px solid #DDD;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.snapshot-action-btn.restore {
  color: #0066CC;
  border-color: #0066CC;
}

.snapshot-action-btn.restore:hover:not(:disabled) {
  background: #0066CC;
  color: #FFF;
}

.snapshot-action-btn.delete {
  color: #CC0000;
  border-color: #CC0000;
}

.snapshot-action-btn.delete:hover:not(:disabled) {
  background: #CC0000;
  color: #FFF;
}

.snapshot-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.snapshot-empty {
  text-align: center;
  padding: 24px;
  color: #999;
  font-size: 13px;
  font-style: italic;
}

/* 自动恢复提示 */
.auto-restore-prompt {
  background: linear-gradient(135deg, #FFF9E6 0%, #FFF3CC 100%);
  border: 1px solid #FFD700;
  border-radius: 8px;
  padding: 16px 20px;
  margin: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.prompt-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.prompt-icon {
  flex-shrink: 0;
  color: #E6A800;
  margin-top: 2px;
}

.prompt-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.prompt-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.prompt-desc {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.prompt-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.prompt-btn {
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.prompt-btn.primary {
  background: #0066CC;
  color: #FFF;
  border-color: #0066CC;
}

.prompt-btn.primary:hover {
  background: #0052AA;
}

.prompt-btn.secondary {
  background: #FFF;
  color: #666;
  border-color: #DDD;
}

.prompt-btn.secondary:hover {
  background: #F5F5F5;
  border-color: #CCC;
}

/* 轮数选择提示中的输入框 */
.rounds-prompt .prompt-content {
  align-items: center;
}

.rounds-input {
  flex-shrink: 0;
  width: 90px;
  padding: 6px 10px;
  border: 1px solid #DDD;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  text-align: center;
  outline: none;
  transition: border-color 0.2s;
}

.rounds-input:focus {
  border-color: #0066CC;
}

.rounds-input:disabled {
  background: #F5F5F5;
  color: #999;
}

.rounds-input::-webkit-outer-spin-button,
.rounds-input::-webkit-inner-spin-button {
  opacity: 1;
}

.btn-icon {
  display: inline-block;
  vertical-align: middle;
}

.action-btn.secondary {
  background: #FFF;
  color: #333;
  border: 1px solid #DDD;
}

.action-btn.secondary:hover:not(:disabled) {
  background: #F5F5F5;
  border-color: #CCC;
}

/* Restore Choice Dialog */
.restore-choice-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeInOverlay 0.2s ease;
}

@keyframes fadeInOverlay {
  from { opacity: 0; }
  to { opacity: 1; }
}

.restore-choice-dialog {
  background: #000;
  border-radius: 12px;
  padding: 28px 32px;
  min-width: 420px;
  max-width: 500px;
  width: 90vw;
  box-shadow: 0 16px 64px rgba(0, 0, 0, 0.5);
  animation: slideUpDialog 0.25s ease;
}

@keyframes slideUpDialog {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.restore-choice-dialog h3 {
  margin: 0 0 6px 0;
  font-size: 18px;
  font-weight: 600;
  color: #FFF;
  letter-spacing: -0.01em;
}

.restore-choice-hint {
  margin: 0 0 20px 0;
  font-size: 13px;
  color: #777;
  font-family: 'JetBrains Mono', monospace;
  word-break: break-all;
}

.restore-choice-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 24px;
}

.restore-choice-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
  padding: 14px 16px;
  border: 1.5px solid #333;
  border-radius: 8px;
  transition: all 0.2s ease;
  background: #111;
}

.restore-choice-option:hover {
  border-color: #666;
  background: #1a1a1a;
}

.restore-choice-option input[type="radio"] {
  margin: 3px 0 0 0;
  width: 16px;
  height: 16px;
  accent-color: #FFF;
  flex-shrink: 0;
}

.option-label {
  font-size: 14px;
  color: #DDD;
  line-height: 1.5;
}

.restore-choice-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.restore-choice-actions button {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #444;
  transition: all 0.2s ease;
  min-width: 72px;
}

.restore-choice-actions .btn-cancel {
  background: transparent;
  color: #999;
}

.restore-choice-actions .btn-cancel:hover {
  background: #222;
  border-color: #666;
  color: #FFF;
}

.restore-choice-actions .btn-confirm {
  background: #FFF;
  color: #000;
  border-color: #FFF;
}

.restore-choice-actions .btn-confirm:hover {
  background: #DDD;
  border-color: #DDD;
}
</style>