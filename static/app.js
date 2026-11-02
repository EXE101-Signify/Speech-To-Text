const $ = id => document.getElementById(id);
let ws, ctx, media, node, source, ping;
fetch('/api/v1/health').then(r => r.json()).then(x => $('model').textContent = 'Model: ' + (x.model_loaded ? 'Ready' : 'Error')).catch(() => $('model').textContent = 'Model: Error');
function cleanup() {
  clearInterval(ping);
  if (node) node.disconnect();
  if (source) source.disconnect();
  if (media) media.getTracks().forEach(t => t.stop());
  if (ctx) ctx.close();
  node = source = media = ctx = null;
  $('mic').textContent = 'Microphone: đã dừng';
  $('start').disabled = false; $('stop').disabled = true;
}
$('start').onclick = async () => {
  $('start').disabled = true;
  try {
    media = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1}});
    ctx = new AudioContext();
    await ctx.audioWorklet.addModule('/static/audio-worklet.js');
    ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/api/v1/stt/stream');
    ws.onopen = () => ws.send(JSON.stringify({type:'start',sample_rate:ctx.sampleRate,channels:1,encoding:'pcm_s16le',language:'vi',api_key:$('key').value || null}));
    ws.onmessage = event => {
      const m = JSON.parse(event.data);
      if (m.type === 'ready') {
        $('connection').textContent = 'WebSocket: đã kết nối';
        $('mic').textContent = 'Microphone: đang thu';
        source = ctx.createMediaStreamSource(media);
        node = new AudioWorkletNode(ctx, 'pcm-processor');
        node.port.onmessage = e => {
          if (e.data === 'flushed') { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type:'stop'})); return; }
          if (ws.readyState === WebSocket.OPEN) {
            if (ws.bufferedAmount > 1024 * 1024) { $('connection').textContent = 'Audio gửi quá chậm'; ws.close(); return; }
            ws.send(e.data);
          }
        };
        source.connect(node); node.connect(ctx.destination);
        $('stop').disabled = false;
        ping = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type:'ping'})); }, 15000);
      } else if (m.type === 'transcript.final') {
        $('text').value += ( $('text').value ? '\n' : '') + m.text;
        $('text').scrollTop = $('text').scrollHeight;
        $('latency').textContent = 'Thời gian xử lý câu: ' + m.processing_time_ms + ' ms';
      } else if (m.type === 'session.completed') ws.close();
      else if (m.type === 'error') { $('connection').textContent = m.message; ws.close(); }
    };
    ws.onerror = () => $('connection').textContent = 'WebSocket: lỗi';
    ws.onclose = () => { cleanup(); $('connection').textContent += ' · đã đóng'; };
  } catch (e) { $('mic').textContent = 'Lỗi: ' + e.message; cleanup(); }
};
$('stop').onclick = () => {
  $('stop').disabled = true;
  if (node) node.port.postMessage('flush');
  if (media) media.getTracks().forEach(t => t.stop());
  if (!node && ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type:'stop'}));
};
$('copy').onclick = () => navigator.clipboard.writeText($('text').value);
$('clear').onclick = () => $('text').value = '';
