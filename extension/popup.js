document.getElementById('capture-btn').addEventListener('click', async () => {
    let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    chrome.scripting.executeScript({
        target: { tabId: tab.id },
        function: extractAndCopyJobDescription,
    }, (results) => {
        if (results && results[0] && results[0].result) {
            document.getElementById('status').style.display = 'block';
            setTimeout(() => {
                // Change to the production URL when deployed
                chrome.tabs.create({ url: 'http://127.0.0.1:8000/' });
            }, 1000);
        }
    });
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
