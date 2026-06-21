document.addEventListener('DOMContentLoaded', () => {
    const serverUrlInput = document.getElementById('server-url-input');
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsPanel = document.getElementById('settings-panel');
    const captureBtn = document.getElementById('capture-btn');

    // Load saved settings
    chrome.storage.sync.get({ serverUrl: 'http://127.0.0.1:8000/' }, (items) => {
        if (serverUrlInput) {
            serverUrlInput.value = items.serverUrl;
        }
    });

    // Save settings on input change
    if (serverUrlInput) {
        serverUrlInput.addEventListener('input', () => {
            let url = serverUrlInput.value.trim();
            if (url && !url.endsWith('/')) {
                url += '/';
            }
            chrome.storage.sync.set({ serverUrl: url });
        });
    }

    // Toggle settings panel
    if (settingsToggle) {
        settingsToggle.addEventListener('click', () => {
            if (settingsPanel.style.display === 'none' || !settingsPanel.style.display) {
                settingsPanel.style.display = 'block';
            } else {
                settingsPanel.style.display = 'none';
            }
        });
    }

    if (captureBtn) {
        captureBtn.addEventListener('click', async () => {
            let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            chrome.scripting.executeScript({
                target: { tabId: tab.id },
                function: extractAndCopyJobDescription,
            }, (results) => {
                if (results && results[0] && results[0].result) {
                    document.getElementById('status').style.display = 'block';
                    setTimeout(() => {
                        chrome.storage.sync.get({ serverUrl: 'http://127.0.0.1:8000/' }, (items) => {
                            chrome.tabs.create({ url: items.serverUrl });
                        });
                    }, 1000);
                }
            });
        });
    }
});

function extractAndCopyJobDescription() {
    // Try to find common job description containers on LinkedIn, Indeed, etc.
    let jdText = "";
    
    const selectors = [
        '.jobs-description__content', // LinkedIn
        '#jobDescriptionText', // Indeed
        '.show-more-less-html__markup' // LinkedIn public
    ];
    
    for (let sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
            jdText = el.innerText;
            break;
        }
    }
    
    // Fallback: just grab the whole body text
    if (!jdText) {
        jdText = document.body.innerText;
    }
    
    // Copy to clipboard
    navigator.clipboard.writeText(jdText).catch(err => {
        console.error('Unable to copy', err);
    });
    
    return true;
}
