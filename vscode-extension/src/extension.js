const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

let mcpServerProcess = null;
let outputChannel = null;

/**
 * Extension 啟動時調用
 */
function activate(context) {
    console.log('Fubon API MCP Server extension is now active');

    // 創建輸出通道
    outputChannel = vscode.window.createOutputChannel('Fubon MCP Server');
    context.subscriptions.push(outputChannel);

    // 註冊命令
    context.subscriptions.push(
        vscode.commands.registerCommand('fubon-mcp.start', startMCPServer)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('fubon-mcp.stop', stopMCPServer)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('fubon-mcp.restart', restartMCPServer)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('fubon-mcp.showLogs', showLogs)
    );
    context.subscriptions.push(
        vscode.commands.registerCommand('fubon-mcp.configure', configureMCPServer)
    );

    // 註冊 MCP Server Provider
    registerMCPServerProvider(context);

    // 自動啟動 (如果配置啟用)
    const config = vscode.workspace.getConfiguration('fubon-mcp');
    if (config.get('autoStart')) {
        setTimeout(() => {
            startMCPServer();
        }, 1000);
    }
}

/**
 * 註冊 MCP Server Provider (for GitHub Copilot integration)
 * 在擴展激活時自動註冊 MCP Server 到 mcp.json
 */
function registerMCPServerProvider(context) {
    try {
        autoRegisterMCPServer();
        outputChannel.appendLine('Fubon MCP Server 已自動註冊');
    } catch (error) {
        outputChannel.appendLine(`自動註冊 MCP Server 失敗: ${error.message}`);
        // 失敗時提示用戶手動配置
        vscode.window.showWarningMessage(
            'Fubon MCP Server 自動註冊失敗，請執行 "Configure Fubon MCP Server" 命令手動配置'
        );
    }
}

/**
 * 自動註冊 MCP Server 到 mcp.json
 * 確保 fubon-api-mcp-server 配置存在於 mcp.json 中
 */
function autoRegisterMCPServer() {
    const mcpConfigPath = getMCPConfigPath();
    const configDir = path.dirname(mcpConfigPath);
    
    outputChannel.appendLine(`檢查 MCP 配置檔案: ${mcpConfigPath}`);
    
    // 確保目錄存在
    if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
        outputChannel.appendLine(`已建立目錄: ${configDir}`);
    }
    
    // 讀取或創建配置
    let mcpConfig = { servers: {}, inputs: [] };
    
    if (fs.existsSync(mcpConfigPath)) {
        try {
            const content = fs.readFileSync(mcpConfigPath, 'utf8');
            mcpConfig = JSON.parse(content);
            if (!mcpConfig.servers) {
                mcpConfig.servers = {};
            }
            if (!mcpConfig.inputs) {
                mcpConfig.inputs = [];
            }
        } catch (error) {
            outputChannel.appendLine(`讀取 MCP 配置失敗，將創建新配置: ${error.message}`);
        }
    }
    
    // 檢查是否已存在 fubon-api-mcp-server 配置
    if (mcpConfig.servers['fubon-api-mcp-server']) {
        outputChannel.appendLine('Fubon MCP Server 配置已存在');
        return;
    }
    
    // 添加 Fubon MCP Server 配置 (使用 python -m 啟動)
    mcpConfig.servers['fubon-api-mcp-server'] = {
        type: 'stdio',
        command: 'python',
        args: ['-m', 'fubon_api_mcp_server.server'],
        env: {
            FUBON_USERNAME: '${input:fubon_username}',
            FUBON_PASSWORD: '${input:fubon_password}',
            FUBON_PFX_PATH: '${input:fubon_pfx_path}',
            FUBON_PFX_PASSWORD: '${input:fubon_pfx_password}',
            FUBON_DATA_DIR: '${input:fubon_data_dir}'
        }
    };
    
    // 更新 inputs (確保不重複)
    const inputIds = new Set(mcpConfig.inputs.map(i => i.id));
    const newInputs = [
        { id: 'fubon_username', type: 'promptString', description: 'FUBON_USERNAME (富邦證券帳號)' },
        { id: 'fubon_password', type: 'promptString', description: 'FUBON_PASSWORD (富邦證券密碼)', password: true },
        { id: 'fubon_pfx_path', type: 'promptString', description: 'FUBON_PFX_PATH (電子憑證路徑 .pfx)' },
        { id: 'fubon_pfx_password', type: 'promptString', description: 'FUBON_PFX_PASSWORD (電子憑證密碼)', password: true },
        { id: 'fubon_data_dir', type: 'promptString', description: 'FUBON_DATA_DIR (數據快取目錄, 預設 ./data)' }
    ];
    
    for (const input of newInputs) {
        if (!inputIds.has(input.id)) {
            mcpConfig.inputs.push(input);
        }
    }
    
    // 寫入配置
    fs.writeFileSync(mcpConfigPath, JSON.stringify(mcpConfig, null, 2), 'utf8');
    outputChannel.appendLine(`MCP 配置已寫入: ${mcpConfigPath}`);
    
    // 顯示成功訊息
    vscode.window.showInformationMessage(
        'Fubon MCP Server 已自動註冊！請重新載入 VS Code 以啟用。',
        '重新載入'
    ).then(selection => {
        if (selection === '重新載入') {
            vscode.commands.executeCommand('workbench.action.reloadWindow');
        }
    });
}

/**
 * 獲取 MCP 配置文件路徑
 */
function getMCPConfigPath() {
    // VS Code MCP 配置位置 (標準 mcp.json)
    // 支援多版本: Code (Stable), Code - Insiders, VSCodium 等
    const homeDir = os.homedir();
    
    // 檢測當前 VS Code 版本
    let vscodeDir = 'Code'; // 預設為 Stable
    if (vscode.env.appName.includes('Insiders')) {
        vscodeDir = 'Code - Insiders';
    } else if (vscode.env.appName.includes('VSCodium')) {
        vscodeDir = 'VSCodium';
    } else if (vscode.env.appName.includes('Cursor')) {
        vscodeDir = 'Cursor';
    }
    
    if (process.platform === 'win32') {
        return path.join(homeDir, 'AppData', 'Roaming', vscodeDir, 'User', 'mcp.json');
    } else if (process.platform === 'darwin') {
        return path.join(homeDir, 'Library', 'Application Support', vscodeDir, 'User', 'mcp.json');
    } else {
        return path.join(homeDir, '.config', vscodeDir, 'User', 'mcp.json');
    }
}

/**
 * 配置 MCP Server
 */
async function configureMCPServer() {
    const config = vscode.workspace.getConfiguration('fubon-mcp');
    
    // 獲取配置
    const username = await vscode.window.showInputBox({
        prompt: '請輸入富邦證券帳號',
        value: config.get('username') || '',
        placeHolder: '您的富邦證券帳號'
    });
    
    if (!username) {
        vscode.window.showWarningMessage('未輸入帳號，取消配置');
        return;
    }
    
    const pfxPath = await vscode.window.showInputBox({
        prompt: '請輸入 PFX 憑證檔案路徑',
        value: config.get('pfxPath') || '',
        placeHolder: 'C:\\path\\to\\your\\certificate.pfx'
    });
    
    if (!pfxPath) {
        vscode.window.showWarningMessage('未輸入憑證路徑，取消配置');
        return;
    }
    
    // 根據平台設定預設路徑提示
    const defaultDataDirHint = process.platform === 'win32'
        ? '%USERPROFILE%\\AppData\\Local\\fubon-mcp\\data'
        : process.platform === 'darwin'
            ? '~/Library/Application Support/fubon-mcp/data'
            : '~/.local/share/fubon-mcp/data';

    const dataDir = await vscode.window.showInputBox({
        prompt: '請輸入數據儲存目錄（留空使用預設路徑）',
        value: config.get('dataDir') || '',
        placeHolder: `空白表示使用預設路徑 ${defaultDataDirHint}`
    });
    
    // 保存配置
    await config.update('username', username, vscode.ConfigurationTarget.Global);
    await config.update('pfxPath', pfxPath, vscode.ConfigurationTarget.Global);
    await config.update('dataDir', dataDir, vscode.ConfigurationTarget.Global);
    
    // 更新 MCP 配置文件
    try {
        await updateMCPConfig(username, pfxPath, dataDir);
        vscode.window.showInformationMessage('Fubon MCP Server 配置已更新！請重新載入 VS Code 以生效。');
    } catch (error) {
        vscode.window.showErrorMessage(`更新 MCP 配置失敗: ${error.message}`);
    }
}

/**
 * 更新 MCP 配置文件 (標準 mcp.json 格式)
 */
async function updateMCPConfig(username, pfxPath, dataDir) {
    const mcpConfigPath = getMCPConfigPath();
    const configDir = path.dirname(mcpConfigPath);
    
    outputChannel.appendLine(`準備寫入 MCP 註冊檔: ${mcpConfigPath}`);
    
    // 確保目錄存在
    if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
        outputChannel.appendLine(`已建立目錄: ${configDir}`);
    }
    
    // 讀取或創建配置
    let mcpConfig = { servers: {}, inputs: [] };
    
    if (fs.existsSync(mcpConfigPath)) {
        try {
            const content = fs.readFileSync(mcpConfigPath, 'utf8');
            mcpConfig = JSON.parse(content);
            if (!mcpConfig.servers) {
                mcpConfig.servers = {};
            }
            if (!mcpConfig.inputs) {
                mcpConfig.inputs = [];
            }
        } catch (error) {
            outputChannel.appendLine(`讀取 MCP 配置失敗: ${error.message}`);
        }
    }
    
    // 添加 Fubon MCP Server 配置 (使用 python -m 啟動)
    mcpConfig.servers['fubon-api-mcp-server'] = {
        type: 'stdio',
        command: 'python',
        args: ['-m', 'fubon_api_mcp_server.server'],
        env: {
            FUBON_USERNAME: '${input:fubon_username}',
            FUBON_PASSWORD: '${input:fubon_password}',
            FUBON_PFX_PATH: '${input:fubon_pfx_path}',
            FUBON_PFX_PASSWORD: '${input:fubon_pfx_password}',
            FUBON_DATA_DIR: '${input:fubon_data_dir}'
        }
    };
    
    // 更新 inputs (確保不重複)
    const inputIds = new Set(mcpConfig.inputs.map(i => i.id));
    const newInputs = [
        { id: 'fubon_username', type: 'promptString', description: 'FUBON_USERNAME (富邦證券帳號)' },
        { id: 'fubon_password', type: 'promptString', description: 'FUBON_PASSWORD (富邦證券密碼)' },
        { id: 'fubon_pfx_path', type: 'promptString', description: 'FUBON_PFX_PATH (電子憑證路徑 .pfx)' },
        { id: 'fubon_pfx_password', type: 'promptString', description: 'FUBON_PFX_PASSWORD (電子憑證密碼)' },
        { id: 'fubon_data_dir', type: 'promptString', description: 'FUBON_DATA_DIR (數據快取目錄, 預設 ./data)' }
    ];
    
    for (const input of newInputs) {
        if (!inputIds.has(input.id)) {
            mcpConfig.inputs.push(input);
        }
    }
    
    // 寫入配置
    fs.writeFileSync(mcpConfigPath, JSON.stringify(mcpConfig, null, 2), 'utf8');
    outputChannel.appendLine(`MCP 註冊檔已寫入: ${mcpConfigPath}`);
}

/**
 * 啟動 MCP Server
 */
async function startMCPServer() {
    if (mcpServerProcess) {
        vscode.window.showWarningMessage('Fubon MCP Server 已經在運行中');
        return;
    }

    try {
        const config = vscode.workspace.getConfiguration('fubon-mcp');
        const username = config.get('username');
        const pfxPath = config.get('pfxPath');
        const dataDir = config.get('dataDir');

        if (!username || !pfxPath) {
            vscode.window.showErrorMessage(
                '請先在設定中配置富邦證券帳號和憑證路徑 (fubon-mcp.username, fubon-mcp.pfxPath)'
            );
            return;
        }

        // 提示輸入密碼
        const password = await vscode.window.showInputBox({
            prompt: '請輸入富邦證券密碼',
            password: true,
            placeHolder: '密碼不會被儲存'
        });

        if (!password) {
            vscode.window.showWarningMessage('未輸入密碼，取消啟動');
            return;
        }

        const pfxPassword = await vscode.window.showInputBox({
            prompt: '請輸入 PFX 憑證密碼 (如果有)',
            password: true,
            placeHolder: '留空表示無密碼'
        });

        outputChannel.appendLine('正在啟動 Fubon MCP Server...');
        outputChannel.show(true);

        // 設定環境變數
        const env = {
            ...process.env,
            FUBON_USERNAME: username,
            FUBON_PASSWORD: password,
            FUBON_PFX_PATH: pfxPath
        };

        // 只在 dataDir 非空時設置
        if (dataDir) {
            env.FUBON_DATA_DIR = dataDir;
        }

        if (pfxPassword) {
            env.FUBON_PFX_PASSWORD = pfxPassword;
        }

        // 設置 Python 環境變數以輸出 UTF-8
        env.PYTHONIOENCODING = 'utf-8';
        env.PYTHONUTF8 = '1';

        // 啟動 Python MCP Server
        mcpServerProcess = spawn('python', ['-m', 'fubon_api_mcp_server.server'], {
            env: env,
            cwd: vscode.workspace.rootPath || process.cwd(),
            shell: false
        });

        mcpServerProcess.stdout.on('data', (data) => {
            try {
                const text = data.toString('utf8');
                outputChannel.appendLine(`[OUT] ${text}`);
            } catch (e) {
                outputChannel.appendLine(`[OUT] ${data.toString()}`);
            }
        });

        mcpServerProcess.stderr.on('data', (data) => {
            try {
                const text = data.toString('utf8');
                outputChannel.appendLine(`[ERR] ${text}`);
            } catch (e) {
                outputChannel.appendLine(`[ERR] ${data.toString()}`);
            }
        });

        mcpServerProcess.on('close', (code) => {
            outputChannel.appendLine(`Fubon MCP Server 已停止 (exit code: ${code})`);
            mcpServerProcess = null;
            
            if (code !== 0) {
                vscode.window.showErrorMessage(`Fubon MCP Server 異常退出 (code: ${code})`);
            }
        });

        mcpServerProcess.on('error', (error) => {
            outputChannel.appendLine(`錯誤: ${error.message}`);
            vscode.window.showErrorMessage(`啟動 MCP Server 失敗: ${error.message}`);
            mcpServerProcess = null;
        });

        vscode.window.showInformationMessage('Fubon MCP Server 已啟動');

    } catch (error) {
        outputChannel.appendLine(`啟動失敗: ${error.message}`);
        vscode.window.showErrorMessage(`啟動 MCP Server 失敗: ${error.message}`);
    }
}

/**
 * 停止 MCP Server
 */
function stopMCPServer() {
    if (!mcpServerProcess) {
        vscode.window.showWarningMessage('Fubon MCP Server 未在運行');
        return;
    }

    outputChannel.appendLine('正在停止 Fubon MCP Server...');
    mcpServerProcess.kill();
    mcpServerProcess = null;
    vscode.window.showInformationMessage('Fubon MCP Server 已停止');
}

/**
 * 重啟 MCP Server
 */
async function restartMCPServer() {
    stopMCPServer();
    // 等待一下確保進程已終止
    await new Promise(resolve => setTimeout(resolve, 1000));
    await startMCPServer();
}

/**
 * 顯示日誌
 */
function showLogs() {
    outputChannel.show(true);
}

/**
 * Extension 停用時調用
 */
function deactivate() {
    if (mcpServerProcess) {
        mcpServerProcess.kill();
    }
}

module.exports = {
    activate,
    deactivate
};
