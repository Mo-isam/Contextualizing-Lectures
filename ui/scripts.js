(function() {
    try {
        var parent = window.parent || window;
        var parentDoc = parent.document;
        
        // Unbind any old listeners if Streamlit triggers a hot-reload
        if (parent.jumpToTimeHandler) {
            parentDoc.removeEventListener('click', parent.jumpToTimeHandler);
        }
        
        // Define the master click handler
        parent.jumpToTimeHandler = function(e) {
            var btn = e.target.closest('.jump-btn');
            if (!btn) return;

            e.preventDefault();
            e.stopPropagation();

            var time = parseFloat(btn.getAttribute('data-time'));
            var audioEl = parentDoc.querySelector('audio'); 
            
            if (audioEl && !isNaN(time)) {
                audioEl.currentTime = time;
                var playPromise = audioEl.play();
                if (playPromise !== undefined) {
                    playPromise.catch(function(err) { console.warn("Autoplay block:", err); });
                }
            } else {
                console.error("Lecture AI: Jump Button Clicked, but no <audio> element found on the page!");
            }
        };

        // Bind the fresh listener
        parentDoc.addEventListener('click', parent.jumpToTimeHandler);
    } catch(e) {
        console.error("Lecture AI: Failed to initialize jump script:", e);
    }
})();