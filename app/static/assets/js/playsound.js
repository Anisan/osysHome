class SyncedAudioPlayer {
  constructor() {
    this.queue = [];
    this.isPlaying = false;
    this.currentAudio = null;
    this.channel = new BroadcastChannel('audio_sync_channel');
    this.lastActiveTime = Date.now();
    this.tabId = Math.random().toString(36).substr(2, 9);
    this.isTabActive = true; // Добавляем флаг активности вкладки
    
    console.log(`Аудиоплеер инициализирован. ID вкладки: ${this.tabId}`);
    
    this.setupListeners();
    this.storeLastActiveTime();
  }

  setupListeners() {
    // Обработчики активности вкладки
    window.addEventListener('focus', () => this.handleFocus());
    window.addEventListener('blur', () => this.handleBlur());
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        this.handleFocus();
      } else {
        this.handleBlur();
      }
    });
    
    // Обработчик сообщений от других вкладок
    this.channel.onmessage = (e) => {
      if (e.data.type === 'activity_update') {
        this.handleActivityUpdate(e.data.time, e.data.tabId, e.data.isActive);
      } else if (e.data.type === 'queue_update') {
        this.handleQueueUpdate(e.data.queue);
      } else if (e.data.type === 'playback_update') {
        this.handlePlaybackUpdate(e.data);
      }
    };
    
    // Периодическая проверка активности
    setInterval(() => this.checkActivity(), 3000);
  }

  checkActivity() {
    const storedTime = parseInt(localStorage.getItem('lastActiveTime')) || 0;
    const activeTabId = localStorage.getItem('lastActiveTabId') || '';
    
    // Если текущая вкладка была последней активной, но сейчас неактивна,
    // и нет других активных вкладок, продолжаем воспроизведение
    if (this.tabId === activeTabId && !this.isTabActive) {
      this.tryPlay();
    }
  }

  handleFocus() {
    this.isTabActive = true;
    const newActiveTime = Date.now();
    this.lastActiveTime = newActiveTime;
    console.log(`Вкладка ${this.tabId} активна`);
    
    this.channel.postMessage({
      type: 'activity_update',
      time: newActiveTime,
      tabId: this.tabId,
      isActive: true
    });
    
    this.storeLastActiveTime();
    this.tryPlay();
  }

  handleBlur() {
    this.isTabActive = false;
    console.log(`Вкладка ${this.tabId} неактивна`);
    
    this.channel.postMessage({
      type: 'activity_update',
      time: this.lastActiveTime,
      tabId: this.tabId,
      isActive: false
    });
    
    // Не останавливаем воспроизведение при потере фокуса
    // Вместо этого полагаемся на checkActivity
  }

  handleActivityUpdate(reportedTime, reportedTabId, isActive) {
    if (reportedTime > this.lastActiveTime) {
      this.lastActiveTime = reportedTime;
      localStorage.setItem('lastActiveTime', reportedTime.toString());
      localStorage.setItem('lastActiveTabId', reportedTabId);
      console.log(`Вкладка ${reportedTabId} теперь последняя активная (активна: ${isActive})`);
      
      // Если другая вкладка стала активной и она действительно активна,
      // и мы сейчас воспроизводим, останавливаем воспроизведение
      if (this.isPlaying && reportedTabId !== this.tabId && isActive) {
        this.stopPlayback();
      }
    }
  }

  handleQueueUpdate(remoteQueue) {
    if (!this.isMostRecentActiveTab()) {
      this.queue = [...remoteQueue];
      console.log('Очередь обновлена:', this.queue);
    }
  }

  handlePlaybackUpdate(data) {
    // Если другая вкладка начала воспроизведение и она последняя активная,
    // и мы не являемся последней активной вкладкой, останавливаем воспроизведение
    if (data.isPlaying && !this.isMostRecentActiveTab() && data.tabId !== this.tabId) {
      this.stopPlayback();
    }
  }

  isMostRecentActiveTab() {
    const storedTime = parseInt(localStorage.getItem('lastActiveTime')) || 0;
    const activeTabId = localStorage.getItem('lastActiveTabId') || '';
    return this.lastActiveTime >= storedTime && this.tabId === activeTabId;
  }

  storeLastActiveTime() {
    localStorage.setItem('lastActiveTime', this.lastActiveTime.toString());
    localStorage.setItem('lastActiveTabId', this.tabId);
  }

  addToQueue(url) {
    if (!url || this.queue.includes(url)) return;
    
    if (!this.isMostRecentActiveTab()) return;
    
    this.queue.push(url);
    console.log(`Добавлен трек: ${url}`);
    this.broadcastQueueUpdate();
    this.tryPlay();
  }

  tryPlay() {
    if (this.isPlaying || this.queue.length === 0) return;
    
    // Разрешаем воспроизведение, если:
    // 1. Это последняя активная вкладка (даже если сейчас неактивна)
    // 2. Или нет других активных вкладок
    if (this.isMostRecentActiveTab() || !this.areOtherTabsActive()) {
      this.playAudio(this.queue[0]);
    }
  }

  areOtherTabsActive() {
    const activeTabId = localStorage.getItem('lastActiveTabId') || '';
    return activeTabId !== '' && activeTabId !== this.tabId;
  }

  playAudio(url) {
    this.isPlaying = true;
    this.currentAudio = new Audio(url);
    
    console.log(`Начинаю воспроизведение: ${url}`);
    this.broadcastPlaybackStatus();
    
    this.currentAudio.play()
      .then(() => {
        this.queue.shift();
        this.broadcastQueueUpdate();
        
        this.currentAudio.onended = () => {
          console.log(`Трек завершен: ${url}`);
          this.isPlaying = false;
          this.broadcastPlaybackStatus();
          this.tryPlay();
        };
      })
      .catch(error => {
        console.error(`Ошибка воспроизведения: ${error}`);
        this.isPlaying = false;
        this.queue.shift();
        this.broadcastQueueUpdate();
        this.tryPlay();
      });
  }

  stopPlayback() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.isPlaying = false;
    console.log('Воспроизведение остановлено');
    this.broadcastPlaybackStatus();
  }

  broadcastQueueUpdate() {
    this.channel.postMessage({
      type: 'queue_update',
      queue: [...this.queue]
    });
  }

  broadcastPlaybackStatus() {
    this.channel.postMessage({
      type: 'playback_update',
      isPlaying: this.isPlaying,
      tabId: this.tabId
    });
  }

  clearQueue() {
    this.queue = [];
    console.log('Очередь очищена');
    this.broadcastQueueUpdate();
  }
}

// Создаем глобальный экземпляр плеера
const audioPlayer = new SyncedAudioPlayer();

// Публичное API для управления плеером
function playSound(url) {
  audioPlayer.addToQueue(url);
}

function stopPlayback() {
  audioPlayer.stopPlayback();
}

function clearPlaylist() {
  audioPlayer.clearQueue();
}