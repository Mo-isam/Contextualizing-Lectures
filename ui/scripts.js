(function() {
    try {
        // Get the main Streamlit document safely
        var parentDoc = window.parent.document || document;
        
        // Safety Check: Only attach this master listener ONCE per session.
        if (parentDoc.__jumpScriptAdded) return;
        parentDoc.__jumpScriptAdded = true;

        // Master Click Listener attached to the entire page
        parentDoc.body.addEventListener('click', function(e) {
            // Check if what the user clicked (or its parent) is a jump button
            var btn = e.target.closest('.jump-btn');
            if (!btn) return; // If it's not a jump button, ignore the click

            e.preventDefault();
            e.stopPropagation();

            var time = parseFloat(btn.getAttribute('data-time'));
            var audioEl = parentDoc.querySelector('audio'); // Find Streamlit's native audio

            if (audioEl && !isNaN(time)) {
                audioEl.currentTime = time;
                
                // Call play directly inside the click event to bypass security blocks
                var playPromise = audioEl.play();
                if (playPromise !== undefined) {
                    playPromise.catch(function(error) {
                        console.warn("Autoplay warning (usually ignorable):", error);
                    });
                }
            }
        });
    } catch(e) {
        console.error("Failed to initialize jump script:", e);
    }
})();