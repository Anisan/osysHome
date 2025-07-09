  
// Функция для форматирования времени в виде строки
function formatTimeDiff(diff) {
    var second = 1000;
    var minute = 1000 * 60;
    var hour = 1000 * 60 * 60;
    var day = 1000 * 60 * 60 * 24;
    var days = Math.floor(diff / day);
    diff -= days * day;
    var hours = Math.floor(diff / hour);
    diff -= hours * hour;
    var minutes = Math.floor(diff / minute);
    diff -= minutes * minute;
    var seconds = Math.floor(diff / second);
    var text = "";
    if (days > 0) text += days + " дн. ";
    if (hours > 0) text += hours + " ч. ";
    if (days==0 && minutes > 0) text += minutes + " мин. ";
    if (days==0 && hours == 0 && seconds > 0) text += seconds + " сек. ";
    if (text == "") 
      text += "только что";
    else {
      if (this.posValue)
        text = text + this.posValue
      else {
        if (diff>0) text += "назад"; 
      }
      if (this.preValue) 
        text = this.preValue + text
      else{
        if (diff<0) text = "Осталось " + text
      }
    }
    return text.trim()
}

class AudioPlayer {
  constructor() {
    this.audioQueue = [];
    this.currentAudio = null;
    this.isTabActive = true;
    this.broadcastChannel = new BroadcastChannel('audioControl');
    this.setupListeners();
  }

  setupListeners() {
    // Отслеживаем видимость вкладки
    document.addEventListener('visibilitychange', () => {
      this.isTabActive = !document.hidden;
      if (this.isTabActive && !this.currentAudio && this.audioQueue.length > 0) {
        this.playNext();
      }
    });

    // Синхронизация между вкладками
    this.broadcastChannel.onmessage = (event) => {
      if (event.data.type === 'start') {
        // Удаляем из очереди файл, который начал играть в другой вкладке
        this.audioQueue = this.audioQueue.filter(item => item.fileUrl !== event.data.fileUrl);
      }
    };
  }

  addToQueue(fileUrl) {
    // Проверяем, нет ли такого файла уже в очереди
    if (this.audioQueue.some(item => item.fileUrl === fileUrl)) {
      return;
    }

    this.audioQueue.push({
      fileUrl,
      timestamp: Date.now()
    });

    if (this.isTabActive && !this.currentAudio) {
      this.playNext();
    }
  }

  playNext() {
    if (!this.isTabActive || this.audioQueue.length === 0) {
      this.currentAudio = null;
      return;
    }

    const nextAudio = this.audioQueue.shift();
    this.currentAudio = new Audio(nextAudio.fileUrl);

    // Уведомляем другие вкладки
    this.broadcastChannel.postMessage({
      type: 'start',
      fileUrl: nextAudio.fileUrl
    });

    this.currentAudio.play();

    this.currentAudio.onended = () => {
      this.currentAudio = null;
      this.playNext();
    };

    this.currentAudio.onerror = () => {
      this.currentAudio = null;
      this.playNext();
    };
  }
}

// Инициализация плеера
const audioPlayer = new AudioPlayer();

// Функция для воспроизведения звука
function playSound(fileUrl) {
  // Проверяем, активна ли вкладка
  if (document.hidden) {
    console.log('Вкладка не активна - звук не будет воспроизведён');
    return;
  }
  
  audioPlayer.addToQueue(fileUrl);
}

// Вешаем глобальный обработчик видимости
window.addEventListener('focus', () => {
  if (!audioPlayer.currentAudio && audioPlayer.audioQueue.length > 0) {
    audioPlayer.playNext();
  }
});
