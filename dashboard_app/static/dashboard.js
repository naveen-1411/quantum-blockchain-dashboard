/* ══════════════════════════════════════════════════════════════
   BLOCKCHAIN DASHBOARD — JAVASCRIPT
   ══════════════════════════════════════════════════════════════ */

// ══════════════════════════════════════════════════════
// Configuration
// ══════════════════════════════════════════════════════

const API_BASE = '/api';
let autoRefreshEnabled = true;
let refreshInterval = 3000; // 3 seconds
let refreshTimerId = null;
let wallets = []; // Store wallet data for address lookup

let charts = {
    keygenChart: null,
    encryptChart: null,
    signatureChart: null,
    latencyChart: null
};

// ══════════════════════════════════════════════════════
// Initialize on Page Load
// ══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard loaded');
    
    // Tab switching
    setupTabSwitching();
    
    // Transaction form
    setupTransactionForm();
    
    // Settings
    setupSettingsHandlers();
    
    // Load initial data
    loadDashboard();
    
    // Setup auto-refresh
    setupAutoRefresh();
    
    // Update footer time
    updateFooterTime();
    setInterval(updateFooterTime, 1000);
});

function setupTabSwitching() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
    
    const transactionTabButtons = document.querySelectorAll('.transaction-tab-btn');
    transactionTabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const subTabName = btn.dataset.subTab;
            switchTransactionTab(subTabName);
        });
    });
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    
    // Mark button as active
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Load data based on tab
    switch (tabName) {
        case 'explorer':
            loadBlocks();
            break;
        case 'transactions':
            loadTransactions();
            loadMempool();
            loadWalletsForForm();
            break;
        case 'wallets':
            loadWallets();
            break;
        case 'nodes':
            loadNodes();
            break;
        case 'metrics':
            loadMetrics();
            break;
        case 'tools':
            getChainStats();
            break;
    }
}

function switchTransactionTab(subTabName) {
    // Hide all sub-tabs
    document.querySelectorAll('.sub-tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all buttons
    document.querySelectorAll('.transaction-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected sub-tab
    document.getElementById(subTabName).classList.add('active');
    
    // Mark button as active
    document.querySelector(`[data-sub-tab="${subTabName}"]`).classList.add('active');
    
    // Load data
    if (subTabName === 'confirmed') {
        loadTransactions();
    } else if (subTabName === 'pending') {
        loadMempool();
    } else if (subTabName === 'create') {
        loadWalletsForForm();
    }
}

// ══════════════════════════════════════════════════════
// Dashboard Loading
// ══════════════════════════════════════════════════════

async function loadDashboard() {
    try {
        // Load header stats
        await loadChainStats();
        
        // Load initial data
        await loadBlocks();
        await loadTransactions();
        await loadMempool();
        await loadWallets();
        await loadNodes();
        await loadMetrics();
        
        console.log('Dashboard loaded successfully');
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

// ══════════════════════════════════════════════════════
// API Calls
// ══════════════════════════════════════════════════════

async function apiCall(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        throw error;
    }
}

async function apiPost(endpoint, data) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        throw error;
    }
}

// ══════════════════════════════════════════════════════
// BLOCKS
// ══════════════════════════════════════════════════════

async function loadBlocks() {
    try {
        const data = await apiCall('/blocks');
        if (!data.success) throw new Error(data.error);
        
        const container = document.getElementById('blocks-container');
        container.innerHTML = '';
        
        if (data.blocks.length === 0) {
            container.innerHTML = '<div class="loading">No blocks yet</div>';
            return;
        }
        
        // Sort by index descending (newest first)
        const sortedBlocks = [...data.blocks].sort((a, b) => b.index - a.index);
        
        sortedBlocks.forEach(block => {
            const blockElement = createBlockElement(block);
            container.appendChild(blockElement);
        });
        
    } catch (error) {
        document.getElementById('blocks-container').innerHTML = 
            `<div class="alert error">Failed to load blocks: ${error.message}</div>`;
    }
}

function createBlockElement(block) {
    const div = document.createElement('div');
    div.className = 'block-card';
    
    const hashShort = block.hash.substring(0, 16) + '…';
    const prevHashShort = block.previous_hash.substring(0, 16) + '…';
    const merkleShort = block.merkle_root.substring(0, 16) + '…';
    
    div.innerHTML = `
        <div class="block-header">
            <div class="block-field">
                <div class="block-field-label">Block Index</div>
                <div class="block-field-value">#${block.index}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Hash</div>
                <div class="block-field-value hash">${hashShort}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Previous Hash</div>
                <div class="block-field-value hash">${prevHashShort}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Merkle Root</div>
                <div class="block-field-value hash">${merkleShort}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Proposer</div>
                <div class="block-field-value">${block.proposer}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Nonce</div>
                <div class="block-field-value">${block.nonce}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Transactions</div>
                <div class="block-field-value">${block.tx_count}</div>
            </div>
            <div class="block-field">
                <div class="block-field-label">Timestamp</div>
                <div class="block-field-value">${block.timestamp_str}</div>
            </div>
        </div>
        ${block.tx_count > 0 ? `
            <div class="block-txs">
                <strong>📋 Transactions (${block.tx_count}):</strong>
                <button class="btn btn-primary" onclick="showBlockDetail(${block.index})" style="margin-top: 10px;">
                    View Details ➜
                </button>
            </div>
        ` : `<div class="block-txs" style="color: var(--text-secondary);">No transactions in this block</div>`}
    `;
    
    return div;
}

async function showBlockDetail(blockIndex) {
    try {
        const data = await apiCall(`/blocks/${blockIndex}`);
        if (!data.success) throw new Error(data.error);
        
        const block = data.block;
        const modal = document.getElementById('block-modal');
        const content = document.getElementById('block-detail-content');
        
        let transactionsHTML = '';
        if (block.transactions.length > 0) {
            transactionsHTML = '<table class="data-table"><thead><tr><th>Hash</th><th>Sender</th><th>Receiver</th><th>Amount</th><th>Fee</th><th>Nonce</th></tr></thead><tbody>';
            block.transactions.forEach(tx => {
                transactionsHTML += `
                    <tr>
                        <td class="hash">${tx.hash.substring(0, 16)}…</td>
                        <td>${tx.sender}</td>
                        <td>${tx.receiver}</td>
                        <td>₹${tx.amount.toFixed(3)}</td>
                        <td>₹${tx.fee.toFixed(6)}</td>
                        <td>${tx.nonce}</td>
                    </tr>
                `;
            });
            transactionsHTML += '</tbody></table>';
        } else {
            transactionsHTML = '<p style="color: var(--text-secondary);">No transactions in this block</p>';
        }
        
        content.innerHTML = `
            <h2>Block #${block.index} Details</h2>
            
            <h3>Block Header</h3>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                <p><strong>Hash:</strong> <code>${block.hash}</code></p>
                <p><strong>Previous Hash:</strong> <code>${block.previous_hash}</code></p>
                <p><strong>Merkle Root:</strong> <code>${block.merkle_root}</code></p>
                <p><strong>Proposer:</strong> ${block.proposer}</p>
                <p><strong>Nonce:</strong> ${block.nonce}</p>
                <p><strong>Difficulty:</strong> ${block.difficulty}</p>
                <p><strong>Version:</strong> ${block.version}</p>
                <p><strong>Timestamp:</strong> ${block.timestamp_str}</p>
            </div>
            
            <h3>Transactions (${block.tx_count})</h3>
            ${transactionsHTML}
        `;
        
        modal.style.display = 'block';
    } catch (error) {
        alert('Failed to load block details: ' + error.message);
    }
}

function closeBlockModal() {
    document.getElementById('block-modal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('block-modal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
}

// ══════════════════════════════════════════════════════
// TRANSACTIONS
// ══════════════════════════════════════════════════════

async function loadTransactions() {
    try {
        const data = await apiCall('/transactions');
        if (!data.success) throw new Error(data.error);
        
        const tbody = document.getElementById('transactions-tbody');
        tbody.innerHTML = '';
        
        if (data.transactions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">No confirmed transactions yet</td></tr>';
            return;
        }
        
        data.transactions.forEach(tx => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="hash">${tx.hash.substring(0, 16)}…</td>
                <td>${tx.sender}</td>
                <td>${tx.receiver}</td>
                <td>₹${tx.amount.toFixed(3)}</td>
                <td>₹${tx.fee.toFixed(6)}</td>
                <td>#${tx.block_index}</td>
                <td><span class="badge badge-success">Confirmed</span></td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (error) {
        document.getElementById('transactions-tbody').innerHTML = 
            `<tr><td colspan="7" class="text-center text-danger">Error loading transactions</td></tr>`;
    }
}

// ══════════════════════════════════════════════════════
// MEMPOOL
// ══════════════════════════════════════════════════════

async function loadMempool() {
    try {
        const data = await apiCall('/mempool');
        if (!data.success) throw new Error(data.error);
        
        const tbody = document.getElementById('mempool-tbody');
        tbody.innerHTML = '';
        
        // Update header
        document.getElementById('pending-txs').textContent = data.total_pending;
        
        if (data.transactions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Mempool is empty</td></tr>';
            return;
        }
        
        data.transactions.forEach((tx, index) => {
            const row = document.createElement('tr');
            const priority = (index + 1);
            row.innerHTML = `
                <td class="hash">${tx.hash.substring(0, 16)}…</td>
                <td>${tx.sender}</td>
                <td>${tx.receiver}</td>
                <td>₹${tx.amount.toFixed(3)}</td>
                <td>₹${tx.fee.toFixed(6)}</td>
                <td>${tx.age_seconds.toFixed(1)}</td>
                <td><span class="badge badge-info">#${priority}</span></td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (error) {
        document.getElementById('mempool-tbody').innerHTML = 
            `<tr><td colspan="7" class="text-center text-danger">Error loading mempool</td></tr>`;
    }
}

// ══════════════════════════════════════════════════════
// WALLETS
// ══════════════════════════════════════════════════════

async function loadWallets() {
    try {
        const data = await apiCall('/wallets');
        if (!data.success) throw new Error(data.error);
        
        const grid = document.getElementById('wallets-grid');
        grid.innerHTML = '';
        
        // Store wallets globally for address lookup
        wallets = data.wallets;
        
        if (data.wallets.length === 0) {
            grid.innerHTML = '<div class="loading">No wallets</div>';
            return;
        }
        
        data.wallets.forEach(wallet => {
            const card = document.createElement('div');
            card.className = 'wallet-card';
            card.innerHTML = `
                <div class="wallet-name">${wallet.name}</div>
                <div class="wallet-address">${wallet.address.substring(0, 20)}…</div>
                <div class="wallet-balance">₹${wallet.balance.toFixed(2)}</div>
                <div class="wallet-info">
                    <div><strong>Role:</strong> ${wallet.role}</div>
                    <div><strong>Keys:</strong> K${wallet.kyber_pub_size}+D${wallet.dilithium_pub_size}</div>
                </div>
            `;
            grid.appendChild(card);
        });
        
    } catch (error) {
        document.getElementById('wallets-grid').innerHTML = 
            `<div class="alert error">Failed to load wallets</div>`;
    }
}

async function loadWalletsForForm() {
    try {
        const data = await apiCall('/wallets');
        if (!data.success) throw new Error(data.error);
        
        const senderSelect = document.getElementById('sender');
        const receiverSelect = document.getElementById('receiver');
        
        // Clear existing options (keep placeholder)
        senderSelect.innerHTML = '<option value="">-- Select Sender --</option>';
        receiverSelect.innerHTML = '<option value="">-- Select Receiver --</option>';
        
        data.wallets.forEach(wallet => {
            const senderOption = document.createElement('option');
            senderOption.value = wallet.name;
            senderOption.textContent = `${wallet.name} (₹${wallet.balance.toFixed(2)})`;
            senderSelect.appendChild(senderOption);
            
            const receiverOption = document.createElement('option');
            receiverOption.value = wallet.name;
            receiverOption.textContent = wallet.name;
            receiverSelect.appendChild(receiverOption);
        });
        
    } catch (error) {
        console.error('Error loading wallets for form:', error);
    }
}

// ══════════════════════════════════════════════════════
// NODES
// ══════════════════════════════════════════════════════

async function loadNodes() {
    try {
        const data = await apiCall('/nodes');
        if (!data.success) throw new Error(data.error);
        
        const tbody = document.getElementById('nodes-tbody');
        tbody.innerHTML = '';
        
        if (data.nodes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No nodes</td></tr>';
            return;
        }
        
        data.nodes.forEach(node => {
            const row = document.createElement('tr');
            const statusBadge = node.status === 'online' ? 
                '<span class="badge badge-success">🟢 Online</span>' : 
                '<span class="badge badge-danger">🔴 Offline</span>';
            
            row.innerHTML = `
                <td><strong>${node.name}</strong></td>
                <td>${node.role.charAt(0).toUpperCase() + node.role.slice(1)}</td>
                <td>${statusBadge}</td>
                <td class="hash">${node.address.substring(0, 20)}…</td>
                <td>₹${node.balance.toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
        
    } catch (error) {
        document.getElementById('nodes-tbody').innerHTML = 
            `<tr><td colspan="5" class="text-center text-danger">Error loading nodes</td></tr>`;
    }
}

// ══════════════════════════════════════════════════════
// METRICS
// ══════════════════════════════════════════════════════

async function loadMetrics() {
    try {
        const data = await apiCall('/metrics');
        if (!data.success) {
            console.warn('Metrics not available yet');
            return;
        }
        
        const metrics = data.metrics;
        
        // Populate table
        const tbody = document.getElementById('metrics-tbody');
        tbody.innerHTML = '';
        
        for (const [operation, stats] of Object.entries(metrics)) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${formatMetricName(operation)}</strong></td>
                <td>${stats.mean.toFixed(3)}</td>
                <td>${stats.median.toFixed(3)}</td>
                <td>${stats.std_dev.toFixed(3)}</td>
                <td>${stats.min.toFixed(3)}</td>
                <td>${stats.max.toFixed(3)}</td>
                <td>${stats.p95.toFixed(3)}</td>
                <td>${stats.count}</td>
            `;
            tbody.appendChild(row);
        }
        
        // Create charts
        createMetricsCharts(metrics);
        
    } catch (error) {
        console.error('Error loading metrics:', error);
    }
}

function formatMetricName(name) {
    const map = {
        'kyber_keygen': 'Kyber Key Generation',
        'dilithium_keygen': 'Dilithium Key Generation',
        'kyber_encrypt': 'Kyber Encryption',
        'kyber_decrypt': 'Kyber Decryption',
        'dilithium_sign': 'Dilithium Signing',
        'dilithium_verify': 'Dilithium Verification',
        'block_mine': 'Block Mining (PoW)',
        'consensus': 'Consensus Round'
    };
    return map[name] || name;
}

function createMetricsCharts(metrics) {
    const chartConfig = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { position: 'bottom' },
            title: { display: false }
        },
        scales: {
            y: { beginAtZero: true }
        }
    };

    // Key Generation Chart
    const keygenLabels = ['Kyber', 'Dilithium'];
    const keygenData = [
        metrics.kyber_keygen?.mean || 0,
        metrics.dilithium_keygen?.mean || 0
    ];
    createChart('keygen-chart', keygenLabels, keygenData, 'Key Generation Time (ms)');

    // Encryption Chart
    const encryptLabels = ['Kyber Encrypt', 'Kyber Decrypt'];
    const encryptData = [
        metrics.kyber_encrypt?.mean || 0,
        metrics.kyber_decrypt?.mean || 0
    ];
    createChart('encrypt-chart', encryptLabels, encryptData, 'Encryption Operations (ms)');

    // Signature Chart
    const signLabels = ['Dilithium Sign', 'Dilithium Verify'];
    const signData = [
        metrics.dilithium_sign?.mean || 0,
        metrics.dilithium_verify?.mean || 0
    ];
    createChart('signature-chart', signLabels, signData, 'Signature Operations (ms)');

    // Latency Chart
    const latencyLabels = ['Kyber Gen', 'Dilithium Gen', 'Encrypt', 'Sign'];
    const latencyData = [
        metrics.kyber_keygen?.p95 || 0,
        metrics.dilithium_keygen?.p95 || 0,
        (metrics.kyber_encrypt?.p95 || 0) + (metrics.kyber_decrypt?.p95 || 0),
        (metrics.dilithium_sign?.p95 || 0) + (metrics.dilithium_verify?.p95 || 0)
    ];
    createChart('latency-chart', latencyLabels, latencyData, 'P95 Latency (ms)');
}

function createChart(canvasId, labels, data, title) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Destroy existing chart if it exists
    if (charts[canvasId + '-instance']) {
        charts[canvasId + '-instance'].destroy();
    }

    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: title,
                data: data,
                backgroundColor: [
                    'rgba(52, 152, 219, 0.8)',
                    'rgba(46, 204, 113, 0.8)',
                    'rgba(155, 89, 182, 0.8)',
                    'rgba(230, 126, 34, 0.8)',
                    'rgba(231, 76, 60, 0.8)'
                ],
                borderColor: [
                    'rgb(52, 152, 219)',
                    'rgb(46, 204, 113)',
                    'rgb(155, 89, 182)',
                    'rgb(230, 126, 34)',
                    'rgb(231, 76, 60)'
                ],
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });

    charts[canvasId + '-instance'] = chart;
}

// ══════════════════════════════════════════════════════
// CHAIN OPERATIONS
// ══════════════════════════════════════════════════════

async function verifyChain() {
    const resultDiv = document.getElementById('verify-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '⏳ Verifying blockchain...';
    resultDiv.className = 'alert info';
    
    try {
        const data = await apiCall('/verify_chain');
        if (!data.success) throw new Error(data.error);
        
        const valid = data.valid;
        const issueCount = data.issue_count;
        
        let html = `
            <strong>${valid ? '✅ Chain is VALID' : '❌ Chain is INVALID'}</strong><br>
            Total Blocks: ${data.total_blocks}<br>
            Total Transactions: ${data.total_transactions}<br>
            Issues Found: ${issueCount}
        `;
        
        if (issueCount > 0) {
            html += '<br><br><strong>Issues:</strong><ul>';
            data.issues.forEach(issue => {
                html += `<li>${issue}</li>`;
            });
            html += '</ul>';
        }
        
        resultDiv.innerHTML = html;
        resultDiv.className = valid ? 'alert success' : 'alert error';
        
    } catch (error) {
        resultDiv.innerHTML = `Error: ${error.message}`;
        resultDiv.className = 'alert error';
    }
}

async function getChainStats() {
    const resultDiv = document.getElementById('stats-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '⏳ Loading statistics...';
    resultDiv.className = 'alert info';
    
    try {
        const data = await apiCall('/chain_stats');
        if (!data.success) throw new Error(data.error);
        
        const stats = data.stats;
        const html = `
            <strong>📊 Blockchain Statistics</strong><br><br>
            <strong>Chain Height:</strong> ${stats.chain_height}<br>
            <strong>Total Blocks:</strong> ${stats.total_blocks}<br>
            <strong>Total Transactions:</strong> ${stats.total_transactions}<br>
            <strong>Genesis Hash:</strong><br><code style="word-break: break-all;">${stats.genesis_hash}</code><br>
            <strong>Latest Block Hash:</strong><br><code style="word-break: break-all;">${stats.latest_block_hash}</code><br>
            <strong>Latest Block Index:</strong> ${stats.latest_block_index}
        `;
        
        resultDiv.innerHTML = html;
        resultDiv.className = 'alert success';
        
    } catch (error) {
        resultDiv.innerHTML = `Error: ${error.message}`;
        resultDiv.className = 'alert error';
    }
}

async function loadChainStats() {
    try {
        const data = await apiCall('/chain_stats');
        if (data.success) {
            document.getElementById('chain-height').textContent = data.stats.chain_height;
            document.getElementById('total-blocks').textContent = data.stats.total_blocks;
            document.getElementById('total-transactions').textContent = data.stats.total_transactions;
        }
    } catch (error) {
        console.error('Error loading chain stats:', error);
    }
}

// ══════════════════════════════════════════════════════
// TRANSACTION CREATION
// ══════════════════════════════════════════════════════

function setupTransactionForm() {

    const form = document.getElementById('transaction-form');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const sender = document.getElementById('sender').value;
        const receiver = document.getElementById('receiver').value;
        const amount = parseFloat(document.getElementById('amount').value);
        const fee = parseFloat(document.getElementById('fee').value) || 0;

        // Basic validation
        if (!sender || !receiver || amount <= 0) {
            showTransactionResult("Please fill all fields correctly", "error");
            return;
        }

        if (sender === receiver) {
            showTransactionResult("Sender and receiver cannot be the same", "error");
            return;
        }

        try {

            const payload = {
                sender: sender,
                receiver: receiver,
                amount: amount,
                fee: fee
            };

            const response = await fetch('/api/transaction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.ok && result.success) {

                // Show successful transaction with new balances
                showTransactionResult(
                    `✅ Transaction successful!<br>
                     ${sender} → ${receiver}: ₹${amount.toFixed(2)}<br>
                     Fee: ₹${fee.toFixed(2)}<br>
                     <br>
                     <strong>Updated Balances:</strong><br>
                     ${sender}: ₹${result.balances[sender].toFixed(2)}<br>
                     ${receiver}: ₹${result.balances[receiver].toFixed(2)}`,
                    "success"
                );

                // Reset form
                form.reset();

                // Reload mempool, wallets, and chain stats
                setTimeout(() => {
                    loadMempool();
                    loadWallets();
                    loadChainStats();
                }, 500);

            } else {

                showTransactionResult(
                    `❌ Error: ${result.error || "Transaction failed"}`,
                    "error"
                );

            }

        } catch (error) {

            showTransactionResult(
                `❌ Failed to create transaction: ${error.message}`,
                "error"
            );

        }
    });
}


// ══════════════════════════════════════════════════════
// DISPLAY RESULT MESSAGE
// ══════════════════════════════════════════════════════

function showTransactionResult(message, type) {

    const resultDiv = document.getElementById("transaction-result");

    resultDiv.style.display = "block";
    resultDiv.innerHTML = message;

    resultDiv.className = `alert ${type}`;

}
// ══════════════════════════════════════════════════════
// SETTINGS
// ══════════════════════════════════════════════════════

function setupSettingsHandlers() {
    const autoRefreshCheckbox = document.getElementById('auto-refresh');
    const refreshIntervalInput = document.getElementById('refresh-interval');
    
    // Load saved settings
    const savedAutoRefresh = localStorage.getItem('autoRefresh');
    const savedInterval = localStorage.getItem('refreshInterval');
    
    if (savedAutoRefresh !== null) {
        autoRefreshEnabled = savedAutoRefresh === 'true';
        autoRefreshCheckbox.checked = autoRefreshEnabled;
    }
    
    if (savedInterval !== null) {
        refreshInterval = parseInt(savedInterval);
        refreshIntervalInput.value = refreshInterval / 1000;
    }
    
    autoRefreshCheckbox.addEventListener('change', (e) => {
        autoRefreshEnabled = e.target.checked;
        localStorage.setItem('autoRefresh', autoRefreshEnabled);
        setupAutoRefresh();
    });
    
    refreshIntervalInput.addEventListener('change', (e) => {
        refreshInterval = parseInt(e.target.value) * 1000;
        localStorage.setItem('refreshInterval', refreshInterval);
        setupAutoRefresh();
    });
}

function saveRefreshSettings() {
    setupSettingsHandlers();
    alert('Settings saved!');
}

function setupAutoRefresh() {
    // Clear existing timer
    if (refreshTimerId) {
        clearInterval(refreshTimerId);
    }
    
    if (autoRefreshEnabled) {
        refreshTimerId = setInterval(() => {
            loadDashboard();
        }, refreshInterval);
        
        console.log(`Auto-refresh enabled: every ${refreshInterval}ms`);
    } else {
        console.log('Auto-refresh disabled');
    }
}

// ══════════════════════════════════════════════════════
// UTILITIES
// ══════════════════════════════════════════════════════

function updateFooterTime() {
    const now = new Date();
    const timeStr = now.toLocaleString();
    document.getElementById('footer-time').textContent = timeStr;
}

// Make functions globally accessible
window.loadBlocks = loadBlocks;
window.loadTransactions = loadTransactions;
window.loadMempool = loadMempool;
window.loadWallets = loadWallets;
window.loadNodes = loadNodes;
window.loadMetrics = loadMetrics;
window.verifyChain = verifyChain;
window.getChainStats = getChainStats;
window.saveRefreshSettings = saveRefreshSettings;
window.showBlockDetail = showBlockDetail;
window.closeBlockModal = closeBlockModal;
window.loadWalletsForForm = loadWalletsForForm;
