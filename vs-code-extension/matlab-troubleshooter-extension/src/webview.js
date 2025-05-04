(function() {
    // Get the VS Code API
    const vscode = acquireVsCodeApi();
    
    // DOM elements
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    // Color themes for chat interface
    const themes = {
        default: {
            userBg: '#0078D4',
            userText: '#ffffff',
            botBg: '#252526',
            botText: '#ffffff',
            codeBg: '#1E1E1E',
            codeText: '#D4D4D4',
            border: '#474747',
            headerBg: '#333333',
            buttonBg: '#0078D4',
            buttonHover: '#106EBE'
        },
        light: {
            userBg: '#0078D4',
            userText: '#ffffff',
            botBg: '#f3f3f3',
            botText: '#333333',
            codeBg: '#f5f5f5',
            codeText: '#333333',
            border: '#cccccc',
            headerBg: '#e6e6e6',
            buttonBg: '#0078D4',
            buttonHover: '#106EBE'
        },
        dark: {
            userBg: '#0E639C',
            userText: '#ffffff',
            botBg: '#2D2D2D',
            botText: '#E8E8E8',
            codeBg: '#1E1E1E',
            codeText: '#D4D4D4',
            border: '#474747',
            headerBg: '#333333',
            buttonBg: '#0E639C',
            buttonHover: '#1177BB'
        }
    };

    // Get current theme (could be extended to detect VS Code theme)
    const currentTheme = 'dark';
    const theme = themes[currentTheme];

    // Apply theme to CSS variables
    document.documentElement.style.setProperty('--user-bg', theme.userBg);
    document.documentElement.style.setProperty('--user-text', theme.userText);
    document.documentElement.style.setProperty('--bot-bg', theme.botBg);
    document.documentElement.style.setProperty('--bot-text', theme.botText);
    document.documentElement.style.setProperty('--code-bg', theme.codeBg);
    document.documentElement.style.setProperty('--code-text', theme.codeText);
    document.documentElement.style.setProperty('--border', theme.border);
    document.documentElement.style.setProperty('--header-bg', theme.headerBg);
    document.documentElement.style.setProperty('--button-bg', theme.buttonBg);
    document.documentElement.style.setProperty('--button-hover', theme.buttonHover);

    // Function to format markdown text
    function formatMarkdown(text) {
        if (!text) return '';
        
        // Handle headers
        text = text.replace(/### (.*?)(?:\n|$)/g, '<h3>$1</h3>\n');
        text = text.replace(/## (.*?)(?:\n|$)/g, '<h2>$1</h2>\n');
        text = text.replace(/# (.*?)(?:\n|$)/g, '<h1>$1</h1>\n');
        
        // Handle code blocks
        text = text.replace(/```(\w*)([\s\S]*?)```/g, function(match, language, code) {
            return `<pre class="code-block"><code class="${language}">${code.trim()}</code></pre>`;
        });
        
        // Handle inline code
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Handle bold text
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Handle italic text
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Handle paragraphs - replace double newlines with paragraph breaks
        text = text.replace(/\n\n/g, '</p><p>');
        
        // Handle single line breaks
        text = text.replace(/\n/g, '<br>');
        
        // Wrap in paragraph tags if not already wrapped
        if (!text.startsWith('<h') && !text.startsWith('<p>')) {
            text = '<p>' + text + '</p>';
        }
        
        return text;
    }

    // Function to add a message to the chat
    function addMessage(text, isUser, messageId = null, sources = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
        
        if (messageId) {
            messageDiv.setAttribute('data-message-id', messageId);
        }
        
        // Format the markdown text
        const formattedText = formatMarkdown(text);
        
        // Create message content container
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = formattedText;
        messageDiv.appendChild(contentDiv);
        
        // Add feedback buttons (thumbs up/down) for bot messages only
        if (!isUser) {
            const feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'message-feedback';
            
            const thumbsUp = document.createElement('button');
            thumbsUp.className = 'feedback-button thumbs-up';
            thumbsUp.innerHTML = '👍';
            thumbsUp.title = 'This answer was helpful';
            
            const thumbsDown = document.createElement('button');
            thumbsDown.className = 'feedback-button thumbs-down';
            thumbsDown.innerHTML = '👎';
            thumbsDown.title = 'This answer needs improvement';
            
            // Add event listeners
            thumbsUp.addEventListener('click', function() {
                provideFeedback(messageDiv, true);
            });
            
            thumbsDown.addEventListener('click', function() {
                provideFeedback(messageDiv, false);
            });
            
            feedbackDiv.appendChild(thumbsUp);
            feedbackDiv.appendChild(thumbsDown);
            messageDiv.appendChild(feedbackDiv);
        }
        
        // Add sources if available
        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'sources';
            sourcesDiv.innerHTML = '<strong>Sources:</strong><br>' + 
                sources.map(source => `- ${source}`).join('<br>');
            messageDiv.appendChild(sourcesDiv);
        }
        
        chatContainer.appendChild(messageDiv);
        
        // Scroll to the bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        return messageDiv;
    }

    // Function to handle feedback
    function provideFeedback(messageDiv, isPositive) {
        // Get the message content
        const content = messageDiv.querySelector('.message-content').textContent;
        const messageId = messageDiv.getAttribute('data-message-id');
        
        // Disable feedback buttons to prevent multiple clicks
        const buttons = messageDiv.querySelectorAll('.feedback-button');
        buttons.forEach(button => {
            button.disabled = true;
            button.style.opacity = 0.5;
        });
        
        // Visual feedback to user
        const activeButton = messageDiv.querySelector(isPositive ? '.thumbs-up' : '.thumbs-down');
        activeButton.style.opacity = 1;
        activeButton.style.transform = 'scale(1.2)';
        
        // Add feedback message
        const feedbackMessageDiv = document.createElement('div');
        feedbackMessageDiv.className = 'feedback-message';
        feedbackMessageDiv.textContent = isPositive ? 
            'Thanks for your feedback!' : 
            'Thanks for your feedback. How can I improve my answer?';
        messageDiv.appendChild(feedbackMessageDiv);
        
        // If negative feedback, prompt for improvements
        if (!isPositive) {
            // Create input for additional feedback
            const feedbackInput = document.createElement('div');
            feedbackInput.className = 'feedback-input-container';
            
            const textInput = document.createElement('input');
            textInput.type = 'text';
            textInput.className = 'feedback-text-input';
            textInput.placeholder = 'Please explain how this answer could be improved...';
            
            const submitButton = document.createElement('button');
            submitButton.className = 'feedback-submit';
            submitButton.textContent = 'Submit';
            
            feedbackInput.appendChild(textInput);
            feedbackInput.appendChild(submitButton);
            messageDiv.appendChild(feedbackInput);
            
            // Focus the input
            textInput.focus();
            
            // Add event listener for submit button
            submitButton.addEventListener('click', function() {
                const feedbackText = textInput.value.trim();
                if (feedbackText) {
                    // Send the feedback to extension
                    vscode.postMessage({
                        command: 'improvementFeedback',
                        originalQuery: content,
                        feedback: feedbackText,
                        messageId: messageId
                    });
                    
                    // Add loading indicator
                    const loadingDiv = document.createElement('div');
                    loadingDiv.className = 'message bot-message';
                    loadingDiv.textContent = 'Improving answer based on your feedback...';
                    chatContainer.appendChild(loadingDiv);
                    
                    // Store the loading div reference to remove it later
                    window.loadingDiv = loadingDiv;
                    
                    // Remove feedback input
                    messageDiv.removeChild(feedbackInput);
                    feedbackMessageDiv.textContent = `Thanks for your feedback: "${feedbackText}"`;
                }
            });
            
            // Also submit on Enter key
            textInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    submitButton.click();
                }
            });
        }
        
        // Send feedback to extension
        vscode.postMessage({
            command: 'feedback',
            messageId: messageId,
            isPositive: isPositive,
            content: content
        });
    }

    // Generate unique IDs for messages
    function generateMessageId() {
        return 'msg_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
    }

    // Function to send a message
    function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        // Add user message to chat
        addMessage(text, true);
        
        // Add loading indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message bot-message loading';
        loadingDiv.innerHTML = '<div class="dot-flashing"></div>';
        chatContainer.appendChild(loadingDiv);
        
        // Send message to extension
        vscode.postMessage({
            command: 'askQuestion',
            text: text
        });
        
        // Clear input
        userInput.value = '';
        
        // Store the loading div reference to remove it later
        window.loadingDiv = loadingDiv;
    }

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Handle messages from the extension
    window.addEventListener('message', event => {
        const message = event.data;
        
        // Remove the loading indicator if it exists
        if (window.loadingDiv) {
            chatContainer.removeChild(window.loadingDiv);
            window.loadingDiv = null;
        }
        
        switch (message.command) {
            case 'response':
                const messageId = generateMessageId();
                addMessage(message.text, false, messageId, message.sources);
                break;
            case 'improvedResponse':
                // Find the message to replace
                const messageToReplace = document.querySelector(`[data-message-id="${message.originalMessageId}"]`);
                if (messageToReplace) {
                    // Replace the content
                    messageToReplace.querySelector('.message-content').innerHTML = formatMarkdown(message.text);
                    
                    // Add an improved tag
                    const improvedTag = document.createElement('div');
                    improvedTag.className = 'improved-tag';
                    improvedTag.textContent = 'Improved';
                    messageToReplace.appendChild(improvedTag);
                    
                    // Remove any feedback elements
                    const feedbackElements = messageToReplace.querySelectorAll('.feedback-message, .feedback-input-container');
                    feedbackElements.forEach(el => messageToReplace.removeChild(el));
                    
                    // Enable feedback buttons again
                    const buttons = messageToReplace.querySelectorAll('.feedback-button');
                    buttons.forEach(button => {
                        button.disabled = false;
                        button.style.opacity = 1;
                        button.style.transform = 'scale(1)';
                    });
                } else {
                    // If message not found, add as new
                    addMessage(message.text, false, generateMessageId(), message.sources);
                }
                break;
            case 'error':
                addMessage(`Error: ${message.text}`, false);
                break;
        }
    });

    // Ensure the user input is focused when the webview loads
    userInput.focus();
})();