(function() {
    try {
        var parent = window.parent || window;
        var parentDoc = parent.document;

        // ── Utility: format seconds to M:SS or H:MM:SS ──
        function fmt(s) {
            s = Math.max(0, Math.floor(s));
            var h = Math.floor(s / 3600);
            var m = Math.floor((s % 3600) / 60);
            var sec = s % 60;
            if (h) return h + ':' + (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
            return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
        }

        // ── Utility: bridge slide number AND time to Streamlit hidden input ──
        function bridgeSlide(slideNum, time) {
            var inp = parentDoc.querySelector('input[aria-label="_timeline_slide_bridge"]');
            if (inp && slideNum) {
                // Focus the input first so Streamlit recognizes it
                inp.focus();
                var setter = Object.getOwnPropertyDescriptor(parent.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, String(slideNum) + ":" + String(time));
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                // Simulate Enter keypress — Streamlit commits text_input on Enter
                inp.dispatchEvent(new KeyboardEvent('keydown',  { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
                inp.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
                inp.dispatchEvent(new KeyboardEvent('keyup',    { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
            }
        }

        // ── Utility: find which slide a given time falls in ──
        function slideAtTime(time, ticks) {
            var best = null;
            for (var i = 0; i < ticks.length; i++) {
                var t = parseFloat(ticks[i].getAttribute('data-time'));
                if (time >= t) best = ticks[i].getAttribute('data-slide');
            }
            return best;
        }

        // ── Utility: get active elements (Streamlit may leave stale DOM nodes during reruns) ──
        function getAudioEl() {
            var audios = parentDoc.querySelectorAll('[data-testid="stAudio"] audio');
            return audios.length > 0 ? audios[audios.length - 1] : parentDoc.querySelector('audio');
        }

        function getPlayerEl() {
            var players = parentDoc.querySelectorAll('.custom-player');
            return players.length > 0 ? players[players.length - 1] : null;
        }

        // ── Client-Side Slide Switching (no Streamlit reruns) ──
        function showSlide(n) {
            n = parseInt(n, 10);
            if (isNaN(n)) return;

            // Switch slide panels
            var viewer = parentDoc.querySelector('.slide-viewer');
            if (viewer) {
                var panels = viewer.querySelectorAll('.slide-panel');
                panels.forEach(function(p) {
                    p.classList.toggle('active', parseInt(p.getAttribute('data-slide'), 10) === n);
                });
                viewer.setAttribute('data-active', n);

                // Update dropdown
                var sel = viewer.querySelector('.slide-select');
                if (sel) sel.value = String(n);
            }

            // Switch notes groups
            var notesViewer = parentDoc.querySelector('.notes-viewer');
            if (notesViewer) {
                var groups = notesViewer.querySelectorAll('.notes-group');
                groups.forEach(function(g) {
                    g.classList.toggle('active', parseInt(g.getAttribute('data-slide'), 10) === n);
                });
                notesViewer.setAttribute('data-active', n);
            }

            // Store in parent so it survives Streamlit reruns
            parent._jsActiveSlide = n;
        }

        // ── Slide Navigation (Prev / Next / Dropdown) ──
        function initSlideNav() {
            var viewer = parentDoc.querySelector('.slide-viewer');
            if (!viewer || viewer._navInit) return;
            viewer._navInit = true;

            var total = parseInt(viewer.getAttribute('data-total'), 10) || 1;

            // Restore JS-driven slide if it exists (survives reruns)
            if (parent._jsActiveSlide) {
                showSlide(parent._jsActiveSlide);
            }

            viewer.addEventListener('click', function(e) {
                var current = parseInt(viewer.getAttribute('data-active'), 10) || 1;
                if (e.target.closest('.slide-prev')) {
                    if (current > 1) showSlide(current - 1);
                } else if (e.target.closest('.slide-next')) {
                    if (current < total) showSlide(current + 1);
                }
            });

            var sel = viewer.querySelector('.slide-select');
            if (sel) {
                sel.addEventListener('change', function() {
                    showSlide(parseInt(sel.value, 10));
                });
            }
        }


        // ── Play-at button handler (note cards) ──
        // Always fetches a FRESH audio reference to avoid stale closures after reruns
        if (parent._jumpHandler) {
            parentDoc.removeEventListener('click', parent._jumpHandler);
        }
        parent._jumpHandler = function(e) {
            var btn = e.target.closest('.jump-btn');
            if (!btn) return;
            e.preventDefault();
            e.stopPropagation();
            var time = parseFloat(btn.getAttribute('data-time'));
            // Always get a fresh reference — the old audio element may be gone
            var audioEl = getAudioEl();
            if (audioEl && !isNaN(time)) {
                var attemptJump = function() {
                    audioEl.currentTime = time;
                    var p = audioEl.play();
                    if (p !== undefined) p.catch(function(err) { console.warn("Play-at autoplay blocked:", err); });
                    audioEl.removeEventListener('loadedmetadata', attemptJump);
                };
                if (audioEl.readyState >= 1) attemptJump();
                else audioEl.addEventListener('loadedmetadata', attemptJump);
            }
        };
        parentDoc.addEventListener('click', parent._jumpHandler);

        // ── Custom Player Initialization ──
        function initPlayer() {
            var audioEl = getAudioEl();
            var player = getPlayerEl();
            if (!audioEl || !player) return;

            // Re-initialize if:
            // 1. Player was never initialized, OR
            // 2. The audio element has changed (Streamlit rerun replaced it)
            if (player._init && player._audioRef === audioEl) return;

            // Tear down old listeners if re-initializing with a new audio element
            if (player._cleanup) {
                player._cleanup();
            }
            player._init = true;
            player._audioRef = audioEl;

            var playBtn = player.querySelector('.cp-play');
            var curEl   = player.querySelector('.cp-current');
            var durEl   = player.querySelector('.cp-duration');
            var track   = player.querySelector('.cp-track');
            var fill    = player.querySelector('.cp-fill');
            var handle  = player.querySelector('.cp-handle');
            var volBtn  = player.querySelector('.cp-vol');
            var ticks   = track.querySelectorAll('.cp-tick');

            function sync() {
                if (!audioEl.duration || !isFinite(audioEl.duration)) return;
                var pct = (audioEl.currentTime / audioEl.duration) * 100;
                fill.style.width = pct + '%';
                handle.style.left = pct + '%';
                curEl.textContent = fmt(audioEl.currentTime);
            }

            // ── Event handlers (stored for cleanup) ──
            function onPlayBtnClick(e) {
                e.preventDefault();
                if (audioEl.paused) { audioEl.play().catch(function(){}); }
                else { audioEl.pause(); }
            }
            function onAudioPlay()  { playBtn.textContent = '⏸'; }
            function onAudioPause() { playBtn.textContent = '▶'; }
            function onTimeUpdate() { sync(); }
            function onLoadedMeta() {
                durEl.textContent = fmt(audioEl.duration);
                sync();
            }

            // Seek on track click — local seek only, no Streamlit bridge
            // This avoids a Streamlit rerun that kills the audio element
            function onTrackClick(e) {
                if (!audioEl.duration || !isFinite(audioEl.duration)) return;
                var rect = track.getBoundingClientRect();
                var pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                audioEl.currentTime = pct * audioEl.duration;
                sync();
                // Resume playback if it was paused
                if (audioEl.paused) {
                    audioEl.play().catch(function(){});
                }
            }

            // Drag to seek
            var dragging = false;
            function onTrackMouseDown(e) { dragging = true; }
            function onDocMouseMove(e) {
                if (!dragging || !audioEl.duration) return;
                var rect = track.getBoundingClientRect();
                var pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                audioEl.currentTime = pct * audioEl.duration;
                sync();
            }
            function onDocMouseUp() {
                if (dragging) {
                    dragging = false;
                    // After drag, resume playback
                    if (audioEl.paused) {
                        audioEl.play().catch(function(){});
                    }
                }
            }

            // Volume toggle
            function onVolBtnClick(e) {
                e.preventDefault();
                audioEl.muted = !audioEl.muted;
                volBtn.textContent = audioEl.muted ? '🔇' : '🔊';
            }

            // ── Attach listeners ──
            playBtn.addEventListener('click', onPlayBtnClick);
            audioEl.addEventListener('play', onAudioPlay);
            audioEl.addEventListener('pause', onAudioPause);
            audioEl.addEventListener('timeupdate', onTimeUpdate);
            audioEl.addEventListener('loadedmetadata', onLoadedMeta);
            track.addEventListener('click', onTrackClick);
            track.addEventListener('mousedown', onTrackMouseDown);
            parentDoc.addEventListener('mousemove', onDocMouseMove);
            parentDoc.addEventListener('mouseup', onDocMouseUp);
            if (volBtn) volBtn.addEventListener('click', onVolBtnClick);

            // ── Cleanup function: removes all listeners so we can safely re-init ──
            player._cleanup = function() {
                playBtn.removeEventListener('click', onPlayBtnClick);
                audioEl.removeEventListener('play', onAudioPlay);
                audioEl.removeEventListener('pause', onAudioPause);
                audioEl.removeEventListener('timeupdate', onTimeUpdate);
                audioEl.removeEventListener('loadedmetadata', onLoadedMeta);
                track.removeEventListener('click', onTrackClick);
                track.removeEventListener('mousedown', onTrackMouseDown);
                parentDoc.removeEventListener('mousemove', onDocMouseMove);
                parentDoc.removeEventListener('mouseup', onDocMouseUp);
                if (volBtn) volBtn.removeEventListener('click', onVolBtnClick);
            };

            // Update play button state if already playing
            if (!audioEl.paused) {
                playBtn.textContent = '⏸';
            }

            // If duration is already available (cached)
            if (audioEl.duration && isFinite(audioEl.duration)) {
                durEl.textContent = fmt(audioEl.duration);
            }

            // Restore play state after rerun
            var initialSeek = parseFloat(player.getAttribute('data-seek'));
            var autoPlay = player.getAttribute('data-autoplay') === 'true';

            if (initialSeek >= 0) {
                var attemptSeek = function() {
                    if (audioEl.readyState >= 1) { // HAVE_METADATA
                        audioEl.currentTime = initialSeek;
                        if (autoPlay) {
                            var p = audioEl.play();
                            if (p !== undefined) p.catch(function(){});
                        }
                        audioEl.removeEventListener('loadedmetadata', attemptSeek);
                        sync();
                    }
                };
                if (audioEl.readyState >= 1) attemptSeek();
                else audioEl.addEventListener('loadedmetadata', attemptSeek);
            } else {
                sync();
            }
        }

        // Run initialization loop to catch Streamlit DOM reruns
        if (parent._playerInitLoop) clearInterval(parent._playerInitLoop);
        parent._playerInitLoop = setInterval(function() {
            initPlayer();
            initSlideNav();
        }, 500);
        initPlayer();
        initSlideNav();

    } catch(e) {
        console.error("Lecture AI: Script init error:", e);
    }
})();