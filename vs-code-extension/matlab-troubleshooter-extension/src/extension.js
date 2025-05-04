const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const axios = require('axios');

/**
 * @param {vscode.ExtensionContext} context
 */
async function activate(context) {
    console.log('MATLAB Troubleshooter is now active!');

    let pythonProcess = null;
    let serverRunning = false;

    let disposable = vscode.commands.registerCommand('matlabTroubleshooter.start', async function () {
        const panel = vscode.window.createWebviewPanel(
            'matlabTroubleshooter',
            'MATLAB Troubleshooter',
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                localResourceRoots: [
                    vscode.Uri.file(path.join(context.extensionPath, 'media')),
                    vscode.Uri.file(path.join(context.extensionPath, 'src')),
                    vscode.Uri.file(path.join(context.extensionPath, 'css'))  // Add this line
                ]
            }
        );

        // Get path to webview script
        const scriptUri = panel.webview.asWebviewUri(vscode.Uri.file(
            path.join(context.extensionPath, 'src', 'webview.js')
        ));
        panel.webview.html = getWebviewContent(panel.webview, context.extensionPath, scriptUri);
        

        // Start the Python server if not already running
        if (!serverRunning) {
            try {
                pythonProcess = await startPythonServer(context);
                
                // Wait for server to start
                let serverReady = false;
                let tries = 0;
                while (!serverReady && tries < 10) {
                    try {
                        await axios.get('http://localhost:5000/health');
                        serverReady = true;
                        console.log('Python server is ready');
                        serverRunning = true;
                    } catch (error) {
                        console.log(`Waiting for server to start... (${tries}/10)`);
                        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
                        tries++;
                    }
                }
                
                if (!serverReady) {
                    vscode.window.showErrorMessage('Failed to start Python server. Check the logs for details.');
                    panel.webview.postMessage({
                        command: 'error',
                        text: 'Failed to start the Python server. Please check the extension logs for details.'
                    });
                    return;
                }
            } catch (error) {
                vscode.window.showErrorMessage(`Failed to start Python server: ${error.message}`);
                panel.webview.postMessage({
                    command: 'error',
                    text: 'Failed to start the Python server. Please check the extension logs for details.'
                });
                return;
            }
        }

        // Handle messages from the webview
        panel.webview.onDidReceiveMessage(
            async message => {
                switch (message.command) {
                    case 'askQuestion':
                        try {
                            console.log(`Sending question to server: ${message.text.substring(0, 50)}...`);
                            const response = await axios.post('http://localhost:5000/troubleshoot', {
                                query: message.text,
                                context: '' // Optional context can be added here
                            });
                            panel.webview.postMessage({
                                command: 'response',
                                text: response.data.answer,
                                sources: response.data.sources || [],
                                score: response.data.score || 0,
                                explanation: response.data.explanation || ''
                            });
                        } catch (error) {
                            console.error('Error connecting to Python server:', error);
                            
                            // Try to restart the server if it crashed
                            if (!pythonProcess || pythonProcess.exitCode !== null) {
                                vscode.window.showInformationMessage('Restarting Python server...');
                                pythonProcess = await startPythonServer(context);
                                serverRunning = false;
                                await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
                            }
                            
                            panel.webview.postMessage({
                                command: 'error',
                                text: 'Error connecting to the Python server. Server is being restarted, please try again in a moment.'
                            });
                        }
                        break;
                    
                    case 'feedback':
                        // Log feedback for now (could be stored or sent to a server)
                        console.log(`Feedback received: ${message.isPositive ? 'Positive' : 'Negative'} for message ID: ${message.messageId}`);
                        break;
                    
                    case 'improvementFeedback':
                        // When user gives feedback for improvement
                        try {
                            // Create a new context with the user feedback
                            const improvementContext = `The previous answer was not helpful. 
                            User feedback: "${message.feedback}". 
                            Please provide an improved answer that addresses this feedback.`;
                            
                            // Send request to the server with original query and improvement context
                            const response = await axios.post('http://localhost:5000/troubleshoot', {
                                query: message.originalQuery,
                                context: improvementContext
                            });
                            
                            // Send the improved response back to the webview
                            panel.webview.postMessage({
                                command: 'improvedResponse',
                                text: response.data.answer,
                                sources: response.data.sources || [],
                                originalMessageId: message.messageId,
                                score: response.data.score || 0,
                                explanation: response.data.explanation || ''
                            });
                        } catch (error) {
                            console.error('Error getting improved response:', error);
                            panel.webview.postMessage({
                                command: 'error',
                                text: 'Failed to get an improved response. Please try again.'
                            });
                        }
                        break;
                }
            },
            undefined,
            context.subscriptions
        );

        // Clean up when the panel is closed
        panel.onDidDispose(() => {
            // We'll keep the server running for now
            // If you want to stop the server on panel close, uncomment below:
            
            if (pythonProcess) {
                pythonProcess.kill();
                pythonProcess = null;
                serverRunning = false;
            }
            
        }, null, context.subscriptions);
    });

    context.subscriptions.push(disposable);
}


async function startPythonServer(context) {
    // Check if the server is already running
    try {
        await axios.get('http://localhost:5000/health', { timeout: 1000 });
        console.log('Python server is already running');
        return null;
    } catch (error) {
        if (error.code !== 'ECONNREFUSED' && !error.message.includes('timeout')) {
            console.log('Server might be running but returned an error:', error.message);
            return null;
        }
        console.log('Starting Python server...');
    }

    // Get the Python extension
    const pythonExtension = vscode.extensions.getExtension('ms-python.python');
    if (!pythonExtension) {
        throw new Error('Python extension is not installed. Please install it to use this extension.');
    }
    
    // Make sure the Python extension is activated
    if (!pythonExtension.isActive) {
        await pythonExtension.activate();
    }

    let pythonPath;
    
    // Method 1: Try to get from the Python extension API (most reliable)
    try {
        const pythonAPI = pythonExtension.exports;
        // This is the most reliable way to get the selected interpreter
        const activeInterpreter = await pythonAPI.getActiveInterpreterPath();
        if (activeInterpreter && fs.existsSync(activeInterpreter)) {
            pythonPath = activeInterpreter;
            console.log(`Found Python path via API: ${pythonPath}`);
        }
    } catch (error) {
        console.error('Error getting Python path from API:', error);
    }
    
    // Method 2: Try getting from VS Code Python extension settings
    if (!pythonPath) {
        try {
            const pythonConfig = vscode.workspace.getConfiguration('python');
            const configPath = pythonConfig.get('defaultInterpreterPath') || 
                              pythonConfig.get('pythonPath');
            
            if (configPath && fs.existsSync(configPath)) {
                pythonPath = configPath;
                console.log(`Found Python path in settings: ${pythonPath}`);
            }
        } catch (error) {
            console.error('Error getting Python path from settings:', error);
        }
    }
    
    // Method 3: Try to find Python in common locations
    if (!pythonPath) {
        console.log('Searching for Python in common locations...');
        const possiblePaths = [
            // Add user's custom path first
            '/media/hp/Void/Haru/Documents/CS671(DL)/Hackathon/venv/bin/python',
            // Then system paths
            '/usr/bin/python3',
            '/usr/local/bin/python3',
            '/usr/bin/python',
            // Windows paths
            'C:\\Python39\\python.exe',
            'C:\\Python310\\python.exe',
            'C:\\Python311\\python.exe',
            // Try to get from PATH environment variable
            'python3',
            'python'
        ];
        
        for (const testPath of possiblePaths) {
            try {
                // For absolute paths, check if they exist
                if (path.isAbsolute(testPath) && fs.existsSync(testPath)) {
                    pythonPath = testPath;
                    console.log(`Found Python at: ${pythonPath}`);
                    break;
                } 
                // For commands like 'python3', try to resolve them using 'which' or 'where'
                else if (!path.isAbsolute(testPath)) {
                    const { execSync } = require('child_process');
                    try {
                        // On Unix-like systems
                        const resolvedPath = execSync(`which ${testPath}`, { encoding: 'utf8' }).trim();
                        if (resolvedPath && fs.existsSync(resolvedPath)) {
                            pythonPath = resolvedPath;
                            console.log(`Resolved Python command to: ${pythonPath}`);
                            break;
                        }
                    } catch (e) {
                        try {
                            // On Windows
                            const resolvedPath = execSync(`where ${testPath}`, { encoding: 'utf8' }).split('\n')[0].trim();
                            if (resolvedPath && fs.existsSync(resolvedPath)) {
                                pythonPath = resolvedPath;
                                console.log(`Resolved Python command to: ${pythonPath}`);
                                break;
                            }
                        } catch (e2) {
                            // Ignore errors from where/which commands
                        }
                    }
                }
            } catch (error) {
                console.log(`Error checking path ${testPath}:`, error.message);
            }
        }
    }

    // If we still don't have a Python path, prompt the user
    if (!pythonPath) {
        const result = await vscode.window.showErrorMessage(
            'Python interpreter not found. Please select a Python interpreter.',
            'Select Python Interpreter'
        );
        
        if (result === 'Select Python Interpreter') {
            // Execute the Python: Select Interpreter command
            await vscode.commands.executeCommand('python.setInterpreter');
            // Try again after the user has selected an interpreter
            return startPythonServer(context);
        } else {
            throw new Error('Python interpreter is required but not found.');
        }
    }

    // Rest of your function to start the Python server...
    // ...


    // Look for api_adapter.py in possible locations
    const possiblePaths = [
        path.join(context.extensionPath, 'src'),
        path.join(context.extensionPath, 'server'),
        path.join(context.extensionPath, '..', 'AI-Troubleshooting-Agent'),
        path.resolve(__dirname, '../../../AI-Troubleshooting-Agent'),
        path.resolve(__dirname, '../../AI-Troubleshooting-Agent'),
        path.resolve(__dirname, '../../../../AI-Troubleshooting-Agent'),
        path.resolve(__dirname, '../../New_arka/AI-Troubleshooting-Agent'),
        path.resolve(__dirname, '../../../New_arka/AI-Troubleshooting-Agent')
    ];

    let adapterPath = null;
    for (const basePath of possiblePaths) {
        const testPath = path.join(basePath, 'api_adapter.py');
        console.log(`Checking path: ${testPath}`);
        if (fs.existsSync(testPath)) {
            adapterPath = testPath;
            console.log(`Found adapter at: ${adapterPath}`);
            break;
        }
    }

    if (!adapterPath) {
        // If we couldn't find it, create the file in the extension directory
        adapterPath = path.join(context.extensionPath, 'server', 'api_adapter.py');
        const adapterDir = path.dirname(adapterPath);
        
        if (!fs.existsSync(adapterDir)) {
            fs.mkdirSync(adapterDir, { recursive: true });
        }
        
        // Write the api_adapter.py file if it doesn't exist
        if (!fs.existsSync(adapterPath)) {
            fs.writeFileSync(adapterPath, getApiAdapterContent());
            
            // Also create a minimal query_processor.py
            const processorPath = path.join(adapterDir, 'query_processor.py');
            fs.writeFileSync(processorPath, getQueryProcessorContent());
            
            console.log(`Created adapter at: ${adapterPath}`);
        }
    }

    vscode.window.showInformationMessage('Starting MATLAB Troubleshooter server...');
    console.log(`Starting Python server with: "${pythonPath}" "${adapterPath}"`);

    // Use spawn instead of exec to avoid buffer issues
    const pythonProcess = spawn(pythonPath, [adapterPath], {
        cwd: path.dirname(adapterPath),
        stdio: ['ignore', 'pipe', 'pipe']
    });
    
    // Set up data handlers with limited buffering
    if (pythonProcess.stdout) {
        pythonProcess.stdout.on('data', (data) => {
            console.log(`Python server output: ${data.toString().trim()}`);
        });
    }
    
    if (pythonProcess.stderr) {
        pythonProcess.stderr.on('data', (data) => {
            console.error(`Python server stderr: ${data.toString().trim()}`);
        });
    }

    pythonProcess.on('error', (error) => {
        console.error(`Failed to start Python server: ${error.message}`);
        vscode.window.showErrorMessage(`Failed to start Python server: ${error.message}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Python server process exited with code ${code}`);
        if (code !== 0 && code !== null) {
            vscode.window.showErrorMessage(`Python server exited with code ${code}`);
        }
    });
    
    return pythonProcess;
}
function getWebviewContent(webview, extensionPath, scriptUri = null) {
    // If scriptUri is not provided, generate it
    if (!scriptUri) {
        scriptUri = webview.asWebviewUri(vscode.Uri.file(
            path.join(extensionPath, 'src', 'webview.js')
        ));
    }
    const logoUri = webview.asWebviewUri(vscode.Uri.file(
        path.join(extensionPath, 'media', 'My_icon.png')
    ));
    // Create CSS URI
    const cssUri = webview.asWebviewUri(vscode.Uri.file(
        path.join(extensionPath, 'css', 'style.css')
    ));

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MATLAB Troubleshooter</title>
    <style>
        :root {
            --user-bg: #0E639C;
            --user-text: #ffffff;
            --bot-bg: #2D2D2D;
            --bot-text: #E8E8E8;
            --code-bg: #1E1E1E;
            --code-text: #D4D4D4;
            --border: #474747;
            --header-bg: #333333;
            --button-bg: #0E639C;
            --button-hover: #1177BB;
            --accent-color: #FF9E64;
            --accent-gradient: linear-gradient(135deg, #FF9E64, #FF7043);
            --logo-shadow: 0 0 10px rgba(255, 158, 100, 0.5);
        }
        
        body {
            font-family: var(--vscode-font-family, 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif);
            padding: 0;
            margin: 0;
            color: var(--vscode-editor-foreground);
            background-color: var(--vscode-editor-background);
            line-height: 1.5;
        }
        
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            max-width: 900px;
            margin: 0 auto;
            padding: 0 15px;
        }
        
        .header {
            padding: 15px 0;
            text-align: center;
            background-color: var(--header-bg);
            border-bottom: 1px solid var(--border);
            margin-bottom: 20px;
            border-radius: 0 0 8px 8px;
            position: relative;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            background-image: linear-gradient(to right, rgba(0, 0, 0, 0.2), transparent, rgba(0, 0, 0, 0.2));
        }
        
        .header h1 {
            margin: 0;
            color: #ffffff;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .logo {
            height: 32px;
            width: auto;
            margin-right: 12px;
            border-radius: 50%;
            box-shadow: var(--logo-shadow);
            animation: pulse 3s infinite alternate;
        }
        
        @keyframes pulse {
            0% {
                box-shadow: 0 0 5px rgba(255, 158, 100, 0.5);
            }
            100% {
                box-shadow: 0 0 15px rgba(255, 158, 100, 0.8);
            }
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 20px;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            background-color: rgba(0, 0, 0, 0.1);
            display: flex;
            flex-direction: column;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 12px 15px;
            border-radius: 8px;
            max-width: 85%;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15);
            position: relative;
            line-height: 1.5;
        }
        
        .user-message {
            background-color: var(--user-bg);
            color: var(--user-text);
            align-self: flex-end;
            margin-left: auto;
            border-bottom-right-radius: 2px;
            border-left: 3px solid var(--accent-color);
        }
        
        .bot-message {
            background-color: var(--bot-bg);
            color: var(--bot-text);
            align-self: flex-start;
            border-bottom-left-radius: 2px;
            border-right: 3px solid var(--accent-color);
            padding-left: 40px; /* Space for the logo */
            position: relative;
        }
        
        .bot-logo {
            position: absolute;
            top: 12px;
            left: 10px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            box-shadow: 0 0 5px rgba(255, 158, 100, 0.4);
        }
        
        .message p {
            margin: 0 0 10px 0;
        }
        
        .message p:last-child {
            margin-bottom: 0;
        }
        
        .message h1, .message h2, .message h3 {
            margin-top: 0;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--accent-color);
            font-weight: 600;
        }
        
        .message pre {
            background-color: var(--code-bg);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 10px 0;
            border-left: 3px solid var(--accent-color);
        }
        
        .message code {
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 0.9em;
            background-color: rgba(0, 0, 0, 0.2);
            padding: 2px 4px;
            border-radius: 3px;
            color: var(--code-text);
        }
        
        .message pre code {
            background-color: transparent;
            padding: 0;
            border-radius: 0;
            color: var(--code-text);
        }
        
        .input-container {
            display: flex;
            margin-bottom: 20px;
            position: relative;
        }
        
        #user-input {
            flex: 1;
            padding: 12px 15px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background-color: var(--bot-bg);
            color: var(--bot-text);
            font-size: 1rem;
            transition: all 0.2s ease;
        }
        
        #user-input:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 2px rgba(255, 158, 100, 0.25);
        }
        
        button {
            padding: 12px 20px;
            margin-left: 10px;
            background-image: var(--accent-gradient);
            color: #ffffff;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        button:hover {
            background-image: linear-gradient(135deg, #FF7043, #FF9E64);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }
        
        .sources {
            font-size: 0.85em;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.6);
        }
        
        /* Loading animation */
        .loading {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 40px;
            padding-left: 40px; /* Space for logo */
            position: relative;
        }
        
        .loading .bot-logo {
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            width: 20px;
            height: 20px;
            border-radius: 50%;
            box-shadow: 0 0 5px rgba(255, 158, 100, 0.4);
        }
        
        .dot-flashing {
            position: relative;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: var(--accent-color);
            color: var(--accent-color);
            animation: dot-flashing 1s infinite linear alternate;
            animation-delay: 0.5s;
        }
        
        .dot-flashing::before, .dot-flashing::after {
            content: '';
            display: inline-block;
            position: absolute;
            top: 0;
        }
        
        .dot-flashing::before {
            left: -15px;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: var(--accent-color);
            color: var(--accent-color);
            animation: dot-flashing 1s infinite alternate;
            animation-delay: 0s;
        }
        
        .dot-flashing::after {
            left: 15px;
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: var(--accent-color);
            color: var(--accent-color);
            animation: dot-flashing 1s infinite alternate;
            animation-delay: 1s;
        }
        
        @keyframes dot-flashing {
            0% {
                background-color: var(--accent-color);
            }
            50%, 100% {
                background-color: rgba(255, 158, 100, 0.2);
            }
        }
        
        /* Message feedback styling */
        .message-feedback {
            display: flex;
            justify-content: flex-end;
            margin-top: 10px;
        }
        
        .feedback-button {
            background: transparent;
            border: none;
            color: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            padding: 5px;
            margin-left: 10px;
            border-radius: 50%;
            transition: all 0.2s ease;
        }
        
        .feedback-button:hover {
            background-color: rgba(255, 255, 255, 0.1);
            transform: scale(1.1);
        }
        
        .feedback-message {
            font-size: 0.85em;
            margin-top: 10px;
            color: rgba(255, 255, 255, 0.7);
            font-style: italic;
        }
        
        .feedback-input-container {
            display: flex;
            margin-top: 10px;
            width: 100%;
        }
        
        .feedback-text-input {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background-color: rgba(0, 0, 0, 0.2);
            color: var(--bot-text);
        }
        
        .feedback-submit {
            padding: 8px 12px;
            margin-left: 8px;
            border-radius: 6px;
        }
        
        .improved-tag {
            position: absolute;
            top: -10px;
            right: 10px;
            background-image: var(--accent-gradient);
            color: white;
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 0.7em;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .loading-canvas {
            width: 200px;
            height: 60px;
            display: block;
            margin: 0 auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><img src="${logoUri}" class="logo" alt="MATLAB Troubleshooter Logo">MATLAB Troubleshooter</h1>
        </div>
        <div id="chat-container" class="chat-container">
            <div class="message bot-message">
                <img src="${logoUri}" class="bot-logo" alt="MATLAB Assistant">
                <div class="message-content">
                    <h3>Welcome to MATLAB Troubleshooter!</h3>
                    <p>I'm your MATLAB Troubleshooting Assistant. I can help you solve MATLAB errors, fix code issues, and provide guidance on best practices.</p>
                    <p>How can I help you today?</p>
                </div>
            </div>
        </div>
        <div class="input-container">
            <input type="text" id="user-input" placeholder="Type your MATLAB problem here...">
            <button id="send-button">Send</button>
        </div>
    </div>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const originalAppend = window.appendMessage;

        window.appendMessage = function(message, isUser) {
            if (isUser) {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'message user-message';
                msgDiv.innerHTML = '<div class="message-content">(message)</div>';
                chatContainer.appendChild(msgDiv);
            } else {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'message bot-message';
                const logoImg = document.createElement('img');
                logoImg.src = "${logoUri}";
                logoImg.className = 'bot-logo';
                logoImg.alt = 'MATLAB Assistant';
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.innerHTML = message;

                msgDiv.appendChild(logoImg);
                msgDiv.appendChild(contentDiv);
                chatContainer.appendChild(msgDiv);
            }
            chatContainer.scrollTop = chatContainer.scrollHeight;
        };

        window.showLoading = function() {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading bot-message';

            const logoImg = document.createElement('img');
            logoImg.src = "${logoUri}";
            logoImg.className = 'bot-logo';
            logoImg.alt = 'MATLAB Assistant';

            const canvas = document.createElement('canvas');
            canvas.className = 'loading-canvas';
            canvas.width = 200;
            canvas.height = 60;

            loadingDiv.appendChild(logoImg);
            loadingDiv.appendChild(canvas);
            chatContainer.appendChild(loadingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            const ctx = canvas.getContext('2d');
            let t = 0;

            function drawWave() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.beginPath();
                for (let x = 0; x <= canvas.width; x++) {
                    const y = canvas.height / 2 + Math.sin((x / canvas.width) * 4 * Math.PI + t) * (canvas.height / 3);
                    ctx.lineTo(x, y);
                }
                ctx.lineWidth = 3;
                ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent-color').trim();
                ctx.stroke();
                t += 0.15;
                requestAnimationFrame(drawWave);
            }
            drawWave();

            return loadingDiv;
        };

        // Load external script
        const script = document.createElement('script');
        script.src = "${scriptUri}";
        document.body.appendChild(script);
    </script>
</body>
</html>`;
}


function getApiAdapterContent() {
    return `from flask import Flask, request, jsonify
from query_processor import process_query
from dotenv import load_dotenv
import logging
import os
import sys

# Set up logging to a file to avoid filling up stderr buffer
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_adapter.log"),
        logging.StreamHandler(sys.stdout)  # Use stdout instead of stderr
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
try:
    load_dotenv()
    logger.info("Environment variables loaded")
except Exception as e:
    logger.error(f"Error loading .env file: {e}")

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint to verify the server is running."""
    logger.info("Health check endpoint called")
    return jsonify({"status": "ok"})

@app.route('/troubleshoot', methods=['POST'])
def troubleshoot():
    """Process a troubleshooting query and return the response."""
    logger.info("Troubleshoot endpoint called")
    
    data = request.json
    if not data or 'query' not in data:
        logger.warning("Missing query parameter")
        return jsonify({"error": "Missing query parameter"}), 400
    
    query = data['query']
    context = data.get('context', "")
    
    logger.info(f"Received query: {query[:50]}...")
    
    try:
        # Process the query
        final_output, score, explanation = process_query(query, context)
        
        # Return the response
        logger.info("Sending response back to client")
        return jsonify({
            "answer": final_output,
            "score": score,
            "explanation": explanation,
            "sources": ["MATLAB Documentation"]  # Adding default sources for UI display
        })
    except Exception as e:
        logger.error(f"Error in troubleshoot endpoint: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Print a message to indicate server is starting
    print("Starting MATLAB Troubleshooter API Server on port 5000...")
    
    # Run the Flask app
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)`;
}

function getQueryProcessorContent() {
    return `import os
import re
import logging

logger = logging.getLogger(__name__)

def process_query(query, context=""):
    """
    Process a MATLAB troubleshooting query and return an answer.
    This is a simplified version for demonstration purposes.
    
    Args:
        query (str): The query from the user
        context (str): Optional context for the query
        
    Returns:
        tuple: (answer, score, explanation)
    """
    logger.info(f"Processing query: {query[:50]}...")
    
    # For improvement feedback, use the context
    if context and "previous answer was not helpful" in context:
        logger.info("Processing improvement feedback")
        return generate_improved_answer(query, context), 0.9, "Improved based on feedback"
    
    # Simple pattern matching for common MATLAB errors
    if re.search(r'(index|indices).*(out of bounds|exceed.*dimensions)', query, re.I):
        return generate_index_error_response(), 0.95, "High confidence index error match"
        
    elif re.search(r'undefined function.*(variable|function)', query, re.I):
        return generate_undefined_function_response(), 0.9, "High confidence undefined function match"
        
    elif re.search(r'(matrix dimensions|dimensions.*agree|size.*match)', query, re.I):
        return generate_dimension_mismatch_response(), 0.85, "Medium-high confidence dimension mismatch"
    
    elif re.search(r'(concatenation|cat|horzcat|vertcat).*dimension', query, re.I):
        return generate_concatenation_error_response(), 0.8, "Medium confidence concatenation error match"
    
    # Fallback for unknown queries
    return generate_general_response(query), 0.6, "General response for unmatched query pattern"

def generate_index_error_response():
    """Generate a response for index out of bounds errors"""
    return """### Index Out of Bounds Error

This is one of the most common MATLAB errors. It occurs when you try to access an element of an array using an index that exceeds the array's dimensions.

#### Common causes:
- Using a constant index that's too large: 'A(10)' when 'A' only has 5 elements
- Using a variable index that becomes too large during iteration
- Off-by-one errors (forgetting that MATLAB indexing starts at 1, not 0)

#### Solutions:
1. **Check your array dimensions** with 'size()' or 'length()'
2. **Use conditional indexing** to avoid out-of-bounds access:
   '''matlab
   if idx <= length(myArray)
       value = myArray(idx);
   end
   '''
3. **Use the 'end' keyword** to refer to the last element:
   '''matlab
   lastElement = myArray(end);
   secondLastElement = myArray(end-1);
   '''

#### Best practices:
- Always validate indices before using them
- Consider using logical indexing instead of numeric indexing where appropriate
- Use the 'min()' function to cap your indices: 'index = min(index, length(array))'"""

def generate_undefined_function_response():
    """Generate a response for undefined function errors"""
    return """### Undefined Function or Variable Error

This error occurs when MATLAB cannot find a function or variable you're trying to use.

#### Common causes:
1. **Typos** in function or variable names
2. **Missing or inaccessible files** that contain the function definition
3. **Path issues** where MATLAB can't find your function files
4. **Scope issues** where variables aren't defined in the current workspace

#### Solutions:
1. **Check spelling and capitalization**
   - MATLAB is case-sensitive: 'myFunction' and 'myfunction' are different
   
2. **Verify function location and MATLAB path**
   - Use 'which functionName to see if MATLAB can find the function
   - Use 'path' to see the current MATLAB search path
   - Add directories to the path: 'addpath('/path/to/your/functions')'
   
3. **For missing variables**
   - Use 'whos' to list all variables in the current workspace
   - Check if the variable was created in another workspace or cleared

4. **For built-in functions**
   - Make sure you haven't accidentally created a variable with the same name as a MATLAB function
   - Check for conflicting function names from different toolboxes

#### Function vs. Script distinction:
If you're trying to call a script as if it were a function, it won't work. Scripts don't accept input arguments or return output arguments the way functions do."""

// Missing implementations for query_processor.py functions

function generate_dimension_mismatch_response() {
    """Generate a response for matrix dimension mismatch errors"""
    return """### Matrix Dimensions Must Agree Error

This error occurs when you try to perform operations on matrices with incompatible dimensions.

#### Common operations that require dimension checking:
1. **Matrix addition/subtraction**: Matrices must have exactly the same dimensions
2. **Matrix multiplication**: For A×B, number of columns in A must equal number of rows in B
3. **Element-wise operations**: Arrays must have compatible dimensions for broadcasting

#### Diagnosing the problem:
'''matlab
% Check sizes of your matrices
size(A)
size(B)
'''

#### Solutions:
1. **Transpose one of your matrices** if appropriate:
   '''matlab
   % Change A*B to A*B' or A'*B
   result = A*B';
   '''

2. **Reshape your matrices**:
   '''matlab
   A = reshape(A, [rows, cols]);
   '''

3. **For element-wise operations, use broadcasting rules**:
   '''matlab
   % Instead of A + B where sizes don't match
   A + repmat(B, size(A,1), 1);
   % Or in newer MATLAB versions
   A + B .* ones(size(A));
   '''

#### Common scenarios:
- Trying to add a row vector to a column vector
- Matrix multiplication with incompatible dimensions
- Using concatenation functions with mismatched dimensions"""

function generate_concatenation_error_response() {
    """Generate a response for concatenation dimension errors"""
    return """### Concatenation Dimension Mismatch Error

This error occurs when trying to concatenate arrays that have incompatible dimensions.

#### Understanding MATLAB concatenation:
1. **Horizontal concatenation** ('horzcat' or '[A, B]'): Arrays must have the same number of rows
2. **Vertical concatenation** ('vertcat' or '[A; B]'): Arrays must have the same number of columns

#### Diagnosing the problem:
'''matlab
% Check sizes of arrays you're trying to concatenate
size(A)
size(B)
'''

#### Common solutions:
1. **Reshape one or more arrays** to match dimensions:
   '''matlab
   B = reshape(B, size(A,1), []);
   result = [A, B]; % Horizontal concatenation
   '''

2. **Transpose if appropriate**:
   '''matlab
   % If B has the wrong orientation
   result = [A, B']; % Horizontal with transposed B
   '''

3. **Pad with zeros or NaN** to match dimensions:
   '''matlab
   % If A is 3x4 and B is 2x4, add a row of zeros to B
   B_padded = [B; zeros(1, size(B,2))];
   result = [A; B_padded];
   '''

#### Best practices:
- Always check dimensions before concatenation
- Use 'cat()' with an explicit dimension parameter for clarity
- When working with cell arrays, remember each cell can have different dimensions"""

function generate_general_response(query) {
    """Generate a general response for unmatched queries"""
    return '### MATLAB Troubleshooting

I couldn't identify a specific MATLAB error pattern in your query: "${query.substring(0, 50)}${query.length > 50 ? '...' : ''}"

Here are some general troubleshooting tips:

#### Basic debugging steps:
1. **Check variable types and dimensions**:
   '''matlab
   % Print variable information
   whos variableName
   % Check size
   size(variableName)
   % Check type
   class(variableName)
   '''

2. **Add breakpoints or use debug mode** to step through your code

3. **Simplify your problem**:
   - Comment out sections of code to isolate the issue
   - Try with simplified inputs
   - Break complex operations into smaller steps

4. **Common MATLAB error patterns**:
   - Index out of bounds: Access to array elements that don't exist
   - Undefined function or variable: Typos or missing files
   - Matrix dimensions: Operations on incompatible matrices
   - File I/O errors: File permissions or incorrect paths
   - Memory issues: Arrays too large for available memory

If you could provide more details about your specific error message or code snippet, I can give you more targeted help.`
}

// Function to deactivate the extension
function deactivate() {
    // Cleanup code here if needed
    // For example, stopping the Python server if it's running
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
        serverRunning = false;
        console.log('MATLAB Troubleshooter server stopped');
    }
}

module.exports = {
    activate,
    deactivate
};