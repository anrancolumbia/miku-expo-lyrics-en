(() => {
  'use strict';

  // --- DOM ---
  const pickerView = document.getElementById('picker-view');
  const pickerCards = document.getElementById('picker-cards');
  const pickerBackBtn = document.getElementById('picker-back-btn');
  const currentSetlistTitle = document.getElementById('current-setlist-title');
  const setlistView = document.getElementById('setlist-view');
  const songView = document.getElementById('song-view');
  const setlistEl = document.getElementById('setlist');
  const concertTitle = document.getElementById('concert-title-text') ||
                       document.getElementById('concert-title');
  const songTitle = document.getElementById('song-title');
  const songArtist = document.getElementById('song-artist');
  const lyricsEl = document.getElementById('lyrics');
  const lyricsScroll = document.getElementById('lyrics-scroll');
  const backBtn = document.getElementById('back-btn');
  const prevBtn = document.getElementById('prev-btn');
  const nextBtn = document.getElementById('next-btn');
  const fsBtn = document.getElementById('fs-btn');
  const pwaHint = document.getElementById('pwa-hint');
  const pwaDismiss = document.getElementById('pwa-dismiss');
  const offsetDisplay = document.getElementById('offset-display');
  const autoscrollBtn = document.getElementById('autoscroll-btn');
  const timedControls = document.getElementById('timed-controls');
  const manualControls = document.getElementById('manual-controls');
  const manualPrev = document.getElementById('manual-prev');
  const manualNext = document.getElementById('manual-next');

  // --- State ---
  let setlistData = null;   // the whole { concert, setlists: [A,B,C] } blob
  let setlist = null;       // { id, name, songs: [{id,title,artist,mode}...] } — currently chosen
  let songMetaCache = {};   // id → {title, artist, mode}
  let currentSong = null;
  let isPlaying = false;
  let startedAt = 0; // performance.now() at press
  let offsetSec = 0;
  let manualIdx = 0;
  let rafHandle = null;
  let lastCurIdx = -1;
  let wakeLock = null;

  // Spotify-style free-scroll: pause auto-centering while user is scrolling.
  let userScrolling = false;
  let userScrollTimer = null;
  const USER_SCROLL_RESUME_MS = 3000;

  // Explicit user toggle (persists across songs within the session)
  let autoScroll = true;

  // --- Helpers ---
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  async function loadSetlist() {
    const r = await fetch('data/setlist.json');
    setlistData = await r.json();
    concertTitle.textContent = setlistData.concert || 'Concert';
    // Prefetch each unique song's meta (title/artist/mode) once.
    const allIds = new Set();
    setlistData.setlists.forEach(sl => sl.songs.forEach(id => allIds.add(id)));
    await Promise.all([...allIds].map(async id => {
      try {
        const sr = await fetch(`data/songs/${id}.json`);
        const sd = await sr.json();
        songMetaCache[id] = { id, title: sd.title, artist: sd.artist, mode: sd.mode };
      } catch (e) {
        songMetaCache[id] = { id, title: id, artist: '', mode: 'manual' };
      }
    }));
    renderPicker();
    // Restore last picked setlist if any
    const saved = localStorage.getItem('miku-setlist');
    if (saved && setlistData.setlists.some(s => s.id === saved)) {
      pickSetlist(saved);
    }
  }

  function renderPicker() {
    pickerCards.innerHTML = '';
    setlistData.setlists.forEach(sl => {
      const card = document.createElement('button');
      card.className = 'picker-card';
      const previewTitles = sl.songs.slice(1, 4)
        .map(id => songMetaCache[id]?.title || id)
        .join(' · ');
      card.innerHTML = `
        <div class="letter">${escape(sl.id)}</div>
        <div class="count">${sl.songs.length} songs · ${escape(sl.name)}</div>
        <div class="preview">Opens with ${escape(songMetaCache[sl.songs[0]]?.title || '')}<br>then ${escape(previewTitles)} …</div>
      `;
      card.addEventListener('click', () => pickSetlist(sl.id));
      pickerCards.appendChild(card);
    });
  }

  function pickSetlist(id) {
    const chosen = setlistData.setlists.find(s => s.id === id);
    if (!chosen) return;
    setlist = {
      id: chosen.id,
      name: chosen.name,
      songs: chosen.songs.map(sid => songMetaCache[sid] || { id: sid, title: sid, artist: '', mode: 'manual' }),
    };
    currentSetlistTitle.textContent = chosen.name;
    localStorage.setItem('miku-setlist', id);
    renderSetlist();
    pickerView.classList.add('hidden');
    setlistView.classList.remove('hidden');
  }

  function backToPicker() {
    setlist = null;
    localStorage.removeItem('miku-setlist');
    setlistView.classList.add('hidden');
    songView.classList.add('hidden');
    pickerView.classList.remove('hidden');
  }

  function renderSetlist() {
    setlistEl.innerHTML = '';
    setlist.songs.forEach((s, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <div class="idx">${i + 1}</div>
        <div class="meta">
          <div class="title-ja">${escape(s.title)}</div>
          <div class="artist">${escape(s.artist || '')}</div>
        </div>
      `;
      li.addEventListener('click', () => openSong(s.id));
      setlistEl.appendChild(li);
    });
  }

  function escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  async function openSong(id) {
    const r = await fetch(`data/songs/${id}.json`);
    currentSong = await r.json();
    resetPlayback();
    songTitle.textContent = currentSong.title;
    songArtist.textContent = currentSong.artist || '';
    const m = currentSong.mode;
    renderLyrics();
    setMode(m);
    setlistView.classList.add('hidden');
    songView.classList.remove('hidden');
    lyricsScroll.scrollTop = 0;
    requestWakeLock();
    // Auto-start timing the moment the song view opens (for timed/pseudo modes).
    if (m === 'timed' || m === 'pseudo') {
      startedAt = performance.now();
      offsetSec = 0;
      isPlaying = true;
      lastCurIdx = -1;
      loop();
    } else {
      setTimeout(() => highlightLine(0), 50);
    }
  }

  function renderLyrics() {
    lyricsEl.innerHTML = '';
    (currentSong.lines || []).forEach((ln, i) => {
      const li = document.createElement('li');
      li.dataset.i = i;
      const ja = document.createElement('div');
      ja.className = 'ja';
      ja.textContent = ln.ja || '';
      li.appendChild(ja);
      if (ln.en) {
        const en = document.createElement('div');
        en.className = 'en';
        en.textContent = ln.en;
        li.appendChild(en);
      }
      li.addEventListener('click', () => {
        // Tap a line to jump to it (handy if drift is bad)
        if (currentSong.mode === 'timed' && isPlaying) {
          const t = currentSong.lines[i].t ?? 0;
          const elapsedWithoutOffset = (performance.now() - startedAt) / 1000;
          offsetSec = t - elapsedWithoutOffset;
          updateOffsetDisplay();
        } else if (currentSong.mode === 'manual') {
          manualIdx = i;
          highlightLine(i);
        }
      });
      lyricsEl.appendChild(li);
    });
  }

  function setMode(mode) {
    // `pseudo` shares controls with `timed`
    const timed = (mode === 'timed' || mode === 'pseudo');
    if (timed) {
      timedControls.classList.remove('hidden');
      manualControls.classList.add('hidden');
    } else {
      timedControls.classList.add('hidden');
      manualControls.classList.remove('hidden');
    }
  }

  function resetPlayback() {
    isPlaying = false;
    startedAt = 0;
    offsetSec = 0;
    manualIdx = 0;
    lastCurIdx = -1;
    updateOffsetDisplay();
    if (rafHandle) cancelAnimationFrame(rafHandle);
    rafHandle = null;
  }

  function updateOffsetDisplay() {
    // Hint only; offset is still adjustable by tapping a line.
    offsetDisplay.textContent = 'Tap any line to jump · re-enter to re-sync';
  }

  // --- Timed mode ---
  // Single button now simply re-aligns the timer to "now" (tap when the stage
  // starts the song). Works for both `timed` and `pseudo` modes.
  function restartTiming() {
    if (!currentSong) return;
    if (currentSong.mode === 'manual') return;
    startedAt = performance.now();
    offsetSec = 0;
    isPlaying = true;
    lastCurIdx = -1;
    if (!rafHandle) loop();
  }

  function loop() {
    if (!isPlaying) return;
    const t = (performance.now() - startedAt) / 1000 + offsetSec;
    const lines = currentSong.lines;
    // binary-ish search for last line with lines[i].t <= t
    let idx = -1;
    for (let i = 0; i < lines.length; i++) {
      if ((lines[i].t ?? Infinity) <= t) idx = i;
      else break;
    }
    if (idx !== lastCurIdx) {
      highlightLine(idx);
      lastCurIdx = idx;
    }
    rafHandle = requestAnimationFrame(loop);
  }

  function highlightLine(idx) {
    const items = lyricsEl.querySelectorAll('li');
    items.forEach(el => el.classList.remove('current'));
    if (idx < 0 || idx >= items.length) return;
    const el = items[idx];
    el.classList.add('current');
    // Don't force-scroll while the user is panning the lyrics, or when autoScroll is off.
    if (userScrolling || !autoScroll) {
      returnBtn.classList.remove('hidden');
      return;
    }
    returnBtn.classList.add('hidden');
    // Center in scroll container
    const containerH = lyricsScroll.clientHeight;
    const elOffset = el.offsetTop;
    const elH = el.offsetHeight;
    const target = elOffset - containerH / 2 + elH / 2;
    lyricsScroll.scrollTo({ top: target, behavior: 'smooth' });
  }

  // Spotify-style: user manually scrolling pauses auto-centering.
  function markUserScroll() {
    userScrolling = true;
    returnBtn.classList.remove('hidden');
    if (userScrollTimer) clearTimeout(userScrollTimer);
    userScrollTimer = setTimeout(() => {
      userScrolling = false;
      // Re-center current line when user stops scrolling
      if (lastCurIdx >= 0) highlightLine(lastCurIdx);
      else returnBtn.classList.add('hidden');
    }, USER_SCROLL_RESUME_MS);
  }

  function returnToCurrent() {
    if (userScrollTimer) { clearTimeout(userScrollTimer); userScrollTimer = null; }
    userScrolling = false;
    returnBtn.classList.add('hidden');
    if (lastCurIdx >= 0) highlightLine(lastCurIdx);
  }

  // --- Manual mode ---
  function manualStep(delta) {
    if (!currentSong) return;
    const n = currentSong.lines.length;
    manualIdx = clamp(manualIdx + delta, 0, n - 1);
    highlightLine(manualIdx);
  }

  // --- Wake lock ---
  async function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (e) {
      console.warn('wake lock failed', e);
    }
  }
  function releaseWakeLock() {
    if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && songView.classList.contains('hidden') === false) {
      requestWakeLock();
    }
  });

  // --- Back ---
  function backToSetlist() {
    resetPlayback();
    songView.classList.add('hidden');
    setlistView.classList.remove('hidden');
    currentSong = null;
    releaseWakeLock();
  }

  // --- User-scroll detection (Spotify-style) ---
  // A "return to current" floating button, inserted once.
  const returnBtn = document.createElement('button');
  returnBtn.id = 'return-btn';
  returnBtn.className = 'hidden';
  returnBtn.textContent = '↓ Jump to current line ↓';
  returnBtn.addEventListener('click', returnToCurrent);
  document.body.appendChild(returnBtn);

  // Detect manual touch/wheel scrolling on the lyrics pane.
  lyricsScroll.addEventListener('touchstart', markUserScroll, { passive: true });
  lyricsScroll.addEventListener('touchmove', markUserScroll, { passive: true });
  lyricsScroll.addEventListener('wheel', markUserScroll, { passive: true });

  // --- Auto-scroll toggle ---
  function toggleAutoScroll() {
    autoScroll = !autoScroll;
    autoscrollBtn.setAttribute('aria-pressed', String(autoScroll));
    const label = autoscrollBtn.querySelector('span');
    if (label) label.textContent = autoScroll ? 'follow' : 'paused';
    if (autoScroll && lastCurIdx >= 0) {
      userScrolling = false;
      if (userScrollTimer) { clearTimeout(userScrollTimer); userScrollTimer = null; }
      highlightLine(lastCurIdx);
    } else {
      returnBtn.classList.remove('hidden');
    }
  }

  // --- Fullscreen ---
  function toggleFullscreen() {
    const doc = document;
    const el = document.documentElement;
    const isFs = doc.fullscreenElement || doc.webkitFullscreenElement;
    if (isFs) {
      (doc.exitFullscreen || doc.webkitExitFullscreen).call(doc);
    } else if (el.requestFullscreen) {
      el.requestFullscreen().catch(() => {
        alert('iPhone Safari does not support the Fullscreen API.\nTap Safari\'s Share → "Add to Home Screen" — opening from that icon hides the browser bars.');
      });
    } else if (el.webkitRequestFullscreen) {
      el.webkitRequestFullscreen();
    } else {
      alert('This browser does not support fullscreen. On iPhone, use Share → Add to Home Screen.');
    }
  }

  // --- PWA hint for iPhone users in Safari (not standalone) ---
  function maybeShowPwaHint() {
    const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
    const isStandalone = window.navigator.standalone === true ||
      window.matchMedia('(display-mode: standalone)').matches;
    const dismissed = localStorage.getItem('pwa-hint-dismissed') === '1';
    if (isIOS && !isStandalone && !dismissed) {
      pwaHint.classList.remove('hidden');
    }
  }
  pwaDismiss.addEventListener('click', () => {
    pwaHint.classList.add('hidden');
    localStorage.setItem('pwa-hint-dismissed', '1');
  });

  // --- Events ---
  fsBtn.addEventListener('click', toggleFullscreen);
  autoscrollBtn.addEventListener('click', toggleAutoScroll);
  pickerBackBtn.addEventListener('click', backToPicker);
  nextBtn.addEventListener('click', () => stepSong(+1));
  prevBtn.addEventListener('click', () => stepSong(-1));

  function stepSong(delta) {
    if (!currentSong || !setlist) return;
    const i = setlist.songs.findIndex(s => s.id === currentSong.id);
    if (i < 0) return;
    const next = setlist.songs[i + delta];
    if (next) openSong(next.id);
  }
  manualPrev.addEventListener('click', () => manualStep(-1));
  manualNext.addEventListener('click', () => manualStep(+1));
  backBtn.addEventListener('click', backToSetlist);

  // Keyboard (desktop testing)
  document.addEventListener('keydown', (e) => {
    if (songView.classList.contains('hidden')) return;
    if (e.key === ' ') { e.preventDefault(); restartTiming(); }
    else if (e.key === 'ArrowRight') manualStep(+1);
    else if (e.key === 'ArrowLeft') manualStep(-1);
    else if (e.key === 'Escape') backToSetlist();
  });

  // --- Boot ---
  maybeShowPwaHint();
  // Register service worker for offline use (first load caches all 34 songs)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(err => {
      console.warn('SW register failed', err);
    });
  }
  loadSetlist().catch(err => {
    setlistEl.innerHTML = `<li style="color:var(--danger);padding:20px">Load failed: ${err.message}</li>`;
  });
})();
