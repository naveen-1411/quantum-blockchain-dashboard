# 🔗 Quantum-Resistant Blockchain Dashboard

A professional web-based dashboard for visualizing and interacting with the post-quantum secure blockchain system.

## 🌟 Features

### 📦 Blockchain Explorer
- View all blocks in the chain with detailed information
- Display block headers (hash, previous hash, merkle root, proposer, nonce)
- Click any block to view all transactions within it
- Real-time chain statistics

### 💳 Transaction Monitor
- **Confirmed Transactions**: View all committed transactions across blocks
- **Pending Transactions (Mempool)**: Monitor transactions waiting to be included in a block
- Fee-priority ordering in mempool
- Transaction details: sender, receiver, amount, fee, nonce, signature status

### 💰 Wallet Dashboard
- Display all wallets in the network (Alice, Bob, Validators)
- Show wallet address, balance, and role
- Key information: Kyber public key size and Dilithium public key size
- Real-time balance updates

### 🌐 Node Network Panel
- View all network nodes with their roles
- Node status (online/offline)
- Role information (sender, receiver, validator)
- Node addresses and balances

### 📊 Performance Metrics
- **Cryptographic Operations**:
  - Kyber key generation time
  - Dilithium key generation time
  - Kyber encryption/decryption latency
  - Dilithium signing/verification latency
- **Interactive Charts**: Bar charts for visual performance analysis
- **Detailed Statistics**: Mean, median, std dev, min, max, P95 percentile

### 🔧 Tools & Operations
- **Verify Blockchain**: Check chain integrity and detect tampering
- **Chain Statistics**: View detailed blockchain metrics
- **Auto-Refresh**: Automatic updates every few seconds (configurable)

### ✅ Transaction Creation
- Create new transactions through the web interface
- Select sender and receiver from available wallets
- Specify amount and fee
- Real-time validation and error messages

## 📋 Requirements

```bash
pip install Flask==2.3.2
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

## 🚀 Quick Start

### Option 1: Run with main_v2.py (Recommended)

1. **Start the blockchain system**:
   ```bash
   python main_v2.py
   ```
   This runs the blockchain demo in the terminal and creates blockchain.db and metrics.db

2. **In a new terminal, start the dashboard server**:
   ```bash
   cd dashboard_app
   python app.py
   ```

3. **Open your browser**:
   ```
   http://localhost:5000
   ```

### Option 2: Run dashboard standalone

If blockchain.db already exists from a previous run:

```bash
cd dashboard_app
python app.py
```

The dashboard will automatically load blockchain data from the database.

## 🏗️ Project Structure

```
dashboard_app/
├── app.py                    # Flask application with REST API endpoints
├── requirements.txt          # Python dependencies
├── templates/
│   └── dashboard.html        # Main dashboard UI
└── static/
    ├── style.css            # Professional styling
    └── dashboard.js         # Frontend logic and API communication
```

## 🔌 REST API Endpoints

All endpoints return JSON data:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/api/blocks` | GET | All blocks in chain |
| `/api/blocks/<index>` | GET | Single block details |
| `/api/transactions` | GET | All confirmed transactions |
| `/api/mempool` | GET | Pending transactions |
| `/api/wallets` | GET | Wallet information |
| `/api/nodes` | GET | Network nodes |
| `/api/metrics` | GET | Performance metrics |
| `/api/chain_stats` | GET | Chain statistics |
| `/api/create_transaction` | POST | Create new transaction |
| `/api/verify_chain` | GET | Verify blockchain integrity |

### Example API Requests

**Get all blocks**:
```bash
curl http://localhost:5000/api/blocks
```

**Get block details**:
```bash
curl http://localhost:5000/api/blocks/1
```

**Get pending transactions**:
```bash
curl http://localhost:5000/api/mempool
```

**Create a transaction**:
```bash
curl -X POST http://localhost:5000/api/create_transaction \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "Alice",
    "receiver": "Bob",
    "amount": 50.0,
    "fee": 0.001
  }'
```

**Verify chain integrity**:
```bash
curl http://localhost:5000/api/verify_chain
```

## 🎨 Dashboard Sections

### 1. Header Statistics
- Chain Height
- Total Blocks
- Total Transactions
- Pending Transactions in Mempool

### 2. Navigation Tabs
- **Explorer**: Blockchain ledger view
- **Transactions**: Confirmed and pending transactions
- **Wallets**: Wallet information and balances
- **Nodes**: Network topology
- **Metrics**: Performance charts and statistics
- **Tools**: Chain verification and utilities

### 3. Auto-Refresh
- Enable/disable automatic updates
- Configurable refresh interval (default: 3 seconds)
- Settings persist in localStorage

## 🔐 Security Notes

The dashboard reads data from:
- **blockchain.db**: SQLite database with committed blocks
- **metrics.db**: SQLite database with performance metrics

Data flows are read-only from these databases. Transaction creation uses cryptographic validation from the blockchain modules.

## 📊 Consensus Visualization

The dashboard displays the PBFT consensus model:
- **PRE-PREPARE**: Proposer broadcasts block to validators
- **PREPARE**: Validators verify and broadcast PREPARE messages
- **COMMIT**: Block committed when ≥ ⌊(2n+1)/3⌋ validators agree

## 🎯 Design Highlights

- **Professional UI**: Clean, modern design suitable for demonstrations
- **Responsive Layout**: Works on desktop and mobile browsers
- **Real-time Updates**: AJAX polling for live data
- **Data Visualization**: Chart.js for performance metrics
- **Accessibility**: Clear typography, high contrast colors
- **User-Friendly**: Intuitive navigation and form inputs

## 🛠️ Customization

### Change Dashboard Port
Edit `app.py` line 567:
```python
app.run(host='localhost', port=5001)  # Change 5000 to 5001
```

### Change Auto-Refresh Interval
In dashboard.html, modify the default:
```html
<input type="number" id="refresh-interval" min="1" step="1" value="3">
```
(Value is in seconds)

### Customize Colors
Edit `static/style.css` CSS variables:
```css
:root {
    --primary-color: #2c3e50;
    --secondary-color: #3498db;
    /* ... */
}
```

## 📝 Logging

The Flask server logs API requests and errors to the console. Check terminal output when starting:

```
[DASHBOARD] Blockchain loaded: Blockchain(height=5, committed_txs=12)
[DASHBOARD] Shared objects set from main_v2
WARNING in app.runserver: This is a development server...
```

## ⚠️ Troubleshooting

### "blockchain.db not found"
- Run `python main_v2.py` first to generate blockchain data
- Check that you're in the correct directory

### "No blocks displayed"
- Verify blockchain.db exists in the project root
- Run `python main_v2.py` to create blocks
- Refresh the dashboard page

### "Metrics empty"
- Run the metrics benchmark in main_v2.py
- Wait for the performance benchmarks section (may take 30 seconds)
- Then refresh the Metrics tab

### Port already in use
- Change the port in `app.py`
- Or kill existing Flask process: `lsof -ti:5000 | xargs kill -9`

## 📖 Architecture

```
┌─────────────────────┐
│   Web Browser       │
│  (http://localhost) │
└──────────┬──────────┘
           │ HTTP/JSON
           ▼
┌─────────────────────┐
│  Flask Application  │
│  (app.py)           │
│  ├─ REST API        │
│  └─ Dashboard HTML  │
└──────────┬──────────┘
           │
      ┌────┴────┐
      ▼         ▼
  ┌────────┐ ┌─────────────┐
  │blockchain_v2.py │ │ SQLite Database │
  │Blockchain Class │ │ (blockchain.db) │
  └────────┘ └─────────────┘
           │
      ┌────┴────┬────────┐
      ▼         ▼        ▼
  ┌────────┐ ┌────────┐ ┌─────────┐
  │ Wallet │ │Mempool │ │ Metrics │
  │ System │ │        │ │Collection│
  └────────┘ └────────┘ └─────────┘
```

## 🎓 Educational Value

This dashboard demonstrates:
- RESTful API design with Flask
- Frontend-backend communication
- Real-time data visualization
- Database querying and JSON serialization
- Bootstrap responsive design
- JavaScript AJAX and Chart.js
- Cryptographic system visualization

## 📄 License

Part of the B.V. Raju Institute of Technology AI&DS Department project.

## 🤝 Integration with Blockchain System

The dashboard integrates seamlessly with:
- ✅ CRYSTALS-Kyber1024 encryption
- ✅ CRYSTALS-Dilithium3 digital signatures
- ✅ PBFT consensus mechanism
- ✅ Merkle tree transaction verification
- ✅ SQLite persistence
- ✅ Proof-of-Work mining
- ✅ Fee-priority mempool

## 🚀 Future Enhancements

Potential additions:
- WebSocket support for real-time updates (vs polling)
- Transaction search and filtering
- Block and transaction export (CSV/JSON)
- Advanced transaction analysis
- Consensus message visualization
- Network simulation controls
- Custom transaction templates

---

**Last Updated**: March 2026
**Version**: 1.0
**Status**: Production Ready
