(function(){
  var curYear, curMonth, selDate = null;
  var wd = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var ms = ['January','February','March','April','May','June',
            'July','August','September','October','November','December'];

  function updateClock(){
    var n = new Date();
    var h = String(n.getHours()).padStart(2,'0');
    var mi = String(n.getMinutes()).padStart(2,'0');
    var s = String(n.getSeconds()).padStart(2,'0');
    document.getElementById('clock').textContent = h + ':' + mi + ':' + s;
  }

  function isoWeek(d){
    var dt = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    dt.setUTCDate(dt.getUTCDate() + 4 - (dt.getUTCDay() || 7));
    var y = dt.getUTCFullYear();
    var start = new Date(Date.UTC(y, 0, 1));
    return Math.ceil((((dt - start) / 864e5) + 1) / 7);
  }

  function monthDays(y, m){
    return new Date(y, m + 1, 0).getDate();
  }

  function render(y, m){
    if (m < 0){ m = 11; y--; }
    if (m > 11){ m = 0; y++; }
    curYear = y; curMonth = m;

    document.getElementById('monthLabel').textContent = ms[m] + ' ' + y;

    var wdHtml = '';
    for (var i = 0; i < 7; i++) wdHtml += '<span>' + wd[i] + '</span>';
    document.getElementById('weekdays').innerHTML = wdHtml;

    var first = new Date(y, m, 1).getDay();
    var dim = monthDays(y, m);
    var prevDim = monthDays(y, m - 1);
    var today = new Date();
    var isTodayMonth = (today.getFullYear() === y && today.getMonth() === m);
    var todayNum = today.getDate();
    var html = '';
    var cell = 0;

    for (var i = first - 1; i >= 0; i--){
      html += '<div class="day other" data-day="' + (prevDim - i) + '" data-other="1">' + (prevDim - i) + '</div>';
      cell++;
    }
    for (var d = 1; d <= dim; d++){
      var cls = 'day';
      if (isTodayMonth && d === todayNum) cls += ' today';
      if (selDate && selDate.getFullYear() === y && selDate.getMonth() === m && selDate.getDate() === d) cls += ' selected';
      html += '<div class="' + cls + '" data-day="' + d + '">' + d + '</div>';
      cell++;
    }
    var rem = (7 - (cell % 7)) % 7;
    for (var i = 1; i <= rem; i++){
      html += '<div class="day other" data-day="' + i + '" data-other="1">' + i + '</div>';
    }
    document.getElementById('days').innerHTML = html;
    showInfo();
  }

  function pickDay(d, other){
    other = other || false;
    if (other){
      if (d > 28){
        render(curYear, curMonth + 1);
        selectDay(d);
      } else {
        render(curYear, curMonth - 1);
        selectDay(d);
      }
      return;
    }
    selectDay(d);
  }

  function selectDay(d){
    selDate = new Date(curYear, curMonth, d);
    var els = document.querySelectorAll('#days .day');
    for (var i = 0; i < els.length; i++) els[i].classList.remove('selected');
    var target = document.querySelector('#days .day[data-day="' + d + '"]:not(.other)');
    if (target) target.classList.add('selected');
    showInfo();
  }

  function showInfo(){
    var el = document.getElementById('info');
    if (!selDate){
      el.innerHTML = '<span class="empty">Click a day for details</span>';
      return;
    }
    var d = selDate;
    var dow = wd[d.getDay()];
    var week = isoWeek(d);
    var yearLabel = (d.getFullYear() === new Date().getFullYear()) ? 'This year' : 'Year ' + d.getFullYear();
    el.innerHTML = '<div class="date">' + dow + ', ' + ms[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear() + '</div>' +
      '<div class="detail">Day ' + d.getDate() + ' of ' + ms[d.getMonth()] + ' \u00B7 Week ' + week + ' \u00B7 ' + yearLabel + '</div>';
  }

  function prevMonth(){ render(curYear, curMonth - 1); }
  function nextMonth(){ render(curYear, curMonth + 1); }
  function goToday(){
    var n = new Date();
    render(n.getFullYear(), n.getMonth());
    selDate = null;
    selectDay(n.getDate());
  }

  document.getElementById('btnPrev').addEventListener('click', prevMonth);
  document.getElementById('btnNext').addEventListener('click', nextMonth);
  document.getElementById('btnToday').addEventListener('click', goToday);

  document.getElementById('days').addEventListener('click', function(e){
    var target = e.target;
    if (!target.classList.contains('day')) return;
    var d = parseInt(target.getAttribute('data-day'), 10);
    var other = target.hasAttribute('data-other');
    pickDay(d, other);
  });

  var n = new Date();
  render(n.getFullYear(), n.getMonth());
  selectDay(n.getDate());
  updateClock();
  setInterval(updateClock, 1000);
})();
