async function inc(){
  var r = await fetch('api/counter', {method:'POST'});
  var d = await r.json();
  document.getElementById('counter').textContent = d.value;
}

async function sendMsg(){
  var val = document.getElementById('msgInput').value;
  var r = await fetch('api/echo', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({msg:val})
  });
  var d = await r.json();
  document.getElementById('msg').textContent = 'You said: ' + d.echo + ' (length: ' + d.len + ')';
}

async function loadInfo(){
  var r = await fetch('api/info');
  var d = await r.json();
  var html = '';
  for (var k in d){
    html += '<div class="row"><span class="lbl">' + esc(k) + '</span><span>' + esc(d[k]) + '</span></div>';
  }
  document.getElementById('info').innerHTML = html;
}

function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
loadInfo();
