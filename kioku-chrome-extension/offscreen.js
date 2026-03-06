// Offscreen document — manages a persistent tab audio stream.
// Background starts/stops the MediaRecorder around each subtitle.

let stream = null;
let recorder = null;
let chunks = [];

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'initStream') {
    initStream(message.streamId).then(sendResponse);
    return true;
  }
  if (message.action === 'startRecording') {
    startRecording();
    sendResponse({ ok: true });
  }
if (message.action === 'stopRecording') {
    stopRecording().then(sendResponse);
    return true;
  }
});

async function initStream(streamId) {
  if (recorder && recorder.state !== 'inactive') recorder.stop();
  if (stream) stream.getTracks().forEach(t => t.stop());
  stream = null;

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId,
        },
      },
    });

    // Pass audio back to speakers so the user can still hear the show
    const audioCtx = new AudioContext();
    audioCtx.createMediaStreamSource(stream).connect(audioCtx.destination);

    console.log('[Kioku offscreen] Stream ready');
    return { ok: true };
  } catch (e) {
    console.log('[Kioku offscreen] initStream error:', e.message);
    return { ok: false, error: e.message };
  }
}

function startRecording() {
  if (!stream) { console.log('[Kioku offscreen] No stream'); return; }
  if (recorder && recorder.state !== 'inactive') recorder.stop();
  chunks = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  recorder.start();
  console.log('[Kioku offscreen] Recording started');
}

async function stopRecording() {
  if (!recorder || recorder.state === 'inactive') {
    console.log('[Kioku offscreen] Nothing to stop');
    return { audio: null };
  }
  return new Promise((resolve) => {
    recorder.onstop = async () => {
      console.log('[Kioku offscreen] Stopped, chunks:', chunks.length);
      if (chunks.length === 0) { resolve({ audio: null }); return; }
      const blob = new Blob(chunks, { type: recorder.mimeType });
      const buffer = await blob.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = '';
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      resolve({ audio: btoa(binary) });
    };
    recorder.stop();
  });
}
