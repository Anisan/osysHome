  
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
