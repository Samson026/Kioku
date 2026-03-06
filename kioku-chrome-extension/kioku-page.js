// Runs in the page's MAIN world — has access to window.netflix.
// Receives seek requests from the isolated-world content script via CustomEvent.

window.addEventListener("kioku-seek", (e) => {
  const timeMs = e.detail?.timeMs;
  if (timeMs == null) return;
  try {
    const vp = netflix.appContext.state.playerApp.getAPI().videoPlayer;
    const id = vp.getAllPlayerSessionIds()[0];
    vp.getVideoPlayerBySessionId(id).seek(Math.round(timeMs));
  } catch (err) {
    console.warn("[Kioku] netflix seek failed:", err.message);
  }
});
