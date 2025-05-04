# MATLAB Troubleshooter VS Code Extension

A VS Code extension for AI-powered MATLAB troubleshooting assistance.

## Features

- Direct access to MATLAB troubleshooting AI from within VS Code
- Chat-based interface for asking MATLAB questions
- Smart responses with references to MATLAB documentation
- Integration with your existing AI troubleshooting agent

## Requirements

- VS Code 1.70.0 or higher
- Python 3.7 or higher
- Your AI Troubleshooting Agent project with app_1.py

## Installation

### Local Development

1. Clone this repository next to your AI-Troubleshooting-Agent folder:
```
parent-directory/
├── AI-Troubleshooting-Agent/
│   └── app_1.py
└── matlab-troubleshooter-extension/
```

2. Open the extension folder in VS Code
3. Run `npm install`
4. Press F5 to start debugging (this will open a new VS Code window with the extension loaded)

## Usage

1. Press `Ctrl+Shift+P` to open the command palette
2. Type "Open MATLAB Troubleshooter" and select it
3. A chat panel will appear where you can ask your MATLAB questions

## Extension Settings

This extension doesn't have any settings yet.

## Known Issues

- The extension assumes that the Python server can run on port 5000
- The extension needs to be installed in a parent directory of your AI-Troubleshooting-Agent

## Release Notes

### 0.1.0

Initial release of MATLAB Troubleshooter extension.