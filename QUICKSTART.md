# 🚀 QUICK START GUIDE — Blockchain Dashboard

## Installation (First Time Only)

### 1. Install Dashboard Dependencies

```bash
# From the project root directory
pip install -r dashboard_app/requirements.txt
```

Or manually:

```bash
pip install Flask==2.3.2
```

### 2. Verify Installation

```bash
# Test Flask is installed
python -c "import flask; print(f'Flask {flask.__version__} installed')"
```

## Running the System

### Windows Users

**Option A: Double-click to launch**

Simply double-click the batch file:
```
launch_dashboard.bat
```

This will:
1. Check dependencies
2. Create blockchain.db if needed
3. Start the Flask dashboard server
4. Open the dashboard in your browser

**Option B: Manual terminal commands**

Terminal 1:
```bash
python main_v2.py
```

Wait for it to complete (10-30 seconds).

Terminal 2:
```bash
cd dashboard_app
python app.py
```

Then open: [http://localhost:5000](http://localhost:5000)

### Mac/Linux Users

**Terminal 1: Start blockchain system**

```bash
python main_v2.py
```

Wait for it to complete.

**Terminal 2: Start dashboard**

```bash
cd dashboard_app
python app.py
```

Then open your browser to: [http://localhost:5000](http://localhost:5000)

**Or run simultaneously**:

Terminal 1:
```bash
python main_v2.py &
sleep 5
cd dashboard_app && python app.py
```

## What You'll See

### After main_v2.py Completes

The terminal will show:
- ✅ Wallets created (Alice, Bob, Validators 1-3)
- ✅ Nodes initialized
- ✅ Transactions created (Alice → Bob)
- ✅ Blocks mined
- ✅ PBFT consensus results
- ✅ Chain integrity verification
- ✅ Performance benchmarks
- ✅ Database statistics

Output ends with:
```
═══════════════════════════════════════════════════
  PHASE 2 DEMO COMPLETE
═══════════════════════════════════════════════════
```

### Dashboard Opens

**Address**: http://localhost:5000

You'll see a professional dashboard with:
- 📊 **Header Statistics**: Chain height, blocks, transactions, pending
- 🔍 **Explorer Tab**: All blocks with details
- 💳 **Transactions Tab**: Confirmed + pending + create form
- 💰 **Wallets Tab**: All wallet info and balances
- 🌐 **Nodes Tab**: Network topology
- 📈 **Metrics Tab**: Performance charts
- 🔧 **Tools Tab**: Chain verification tools

## Dashboard Features

### 1️⃣ Blockchain Explorer
- Click any block to see full details
- View transaction hashes, senders, receivers
- See block headers: hash, merkle root, nonce, proposer

### 2️⃣ Transaction Creation
1. Go to **Transactions** tab
2. Click **Create New** sub-tab
3. Select sender and receiver
4. Enter amount and fee
5. Click **✓ Create Transaction**
6. New transaction appears in mempool

### 3️⃣ Verify Chain Integrity
1. Go to **Tools** tab
2. Click **Verify Chain** button
3. System reports:
   - ✅ Chain valid OR ❌ Issues found
   - Total blocks and transactions
   - Any tampering detected

### 4️⃣ View Performance Metrics
1. Go to **Metrics** tab
2. See charts for:
   - Kyber/Dilithium key generation
   - Encryption/decryption times
   - Signature operations
   - P95 latencies

### 5️⃣ Auto-Refresh
1. Go to **Tools** tab
2. Enable/disable **Auto-refresh**
3. Set refresh interval (default: 3 seconds)
4. Settings save automatically

## Common Tasks

### Create a Transaction

1. **Transactions** tab → **Create New**
2. Fill form:
   - Sender: Alice
   - Receiver: Bob
   - Amount: 50.50
   - Fee: 0.001
3. Click **✓ Create Transaction**
4. See ✅ Success message
5. Transaction appears in mempool after ~1 second

### View Block Details

1. **Explorer** tab
2. Scroll to any block
3. Click **View Details ➜** button
4. See full block with all transactions

### Check Wallet Balance

1. **Wallets** tab
2. Cards show:
   - Wallet name
   - Address
   - Current balance (₹)
   - Role (User/Validator)
   - Key sizes

### Monitor Mempool

1. **Transactions** tab → **Pending (Mempool)**
2. See pending transactions sorted by fee
3. Priority #1 = next to be mined
4. Age shows how long pending

## Troubleshooting

### "Can't connect to http://localhost:5000"

**Issue**: Dashboard server didn't start

**Solution**:
- Check that Flask is installed: `pip install Flask==2.3.2`
- Check terminal for error messages
- Try port 5001: Edit `dashboard_app/app.py` line 567:
  ```python
  app.run(host='localhost', port=5001)  # Changed from 5000
  ```

### "No blocks showing"

**Issue**: blockchain.db not found or empty

**Solution**:
- Run `python main_v2.py` first
- Wait for it to complete
- Then start dashboard
- Refresh browser page

### "Port 5000 already in use"

**Issue**: Another application is using port 5000

**Solution - Windows**:
```bash
# Find process using port 5000
netstat -ano | findstr :5000

# Kill it (replace PID)
taskkill /PID 12345 /F
```

**Solution - Mac/Linux**:
```bash
lsof -ti:5000 | xargs kill -9
```

Or change port in `dashboard_app/app.py`.

### "Metrics tab is empty"

**Issue**: Metrics not recorded yet

**Solution**:
- Metrics are populated during main_v2.py benchmarks (last section)
- Run main_v2.py to completion
- Then refresh dashboard Metrics tab

### "Transaction creation fails"

**Issue**: Sender/receiver selection or balance issue

**Check**:
1. Sender and receiver are different
2. Sender has enough balance (amount + fee)
3. Both wallets exist
4. Check browser console for errors

### "All wallets have 0 balance"

**Note**: This is normal!
- Validator wallets start with 0 balance (they don't send transactions)
- Alice: 1000.00, Bob: 500.00
- Balances only update after new blocks are confirmed with their new transactions

## File Structure

What was created:

```
dashboard_app/
├── app.py                      # Flask server + REST API
├── requirements.txt            # Dependencies
├── README.md                   # Detailed documentation
├── templates/
│   └── dashboard.html         # Web UI (HTML 5)
└── static/
    ├── style.css              # Professional styling (CSS 3)
    └── dashboard.js           # Interactivity + charts (JavaScript)
```

Plus:
- `launch_dashboard.bat` - Windows launcher
- `INTEGRATION_GUIDE.md` - Advanced integration info
- `QUICKSTART.md` - This file

## Architecture

```
User's Browser
      ↓ (HTTP)
   Flask Server (port 5000)
      ↓ (Python imports)
   Blockchain Module
   ├─ blockchain_v2.py
   ├─ wallet.py
   ├─ mempool.py
   ├─ metrics.py
   ├─ node_v2.py
   └─ consensus.py
      ↓
   SQLite Databases
   ├─ blockchain.db (blocks & transactions)
   └─ metrics.db (performance data)
```

## Browser Support

- ✅ Chrome/Chromium (85+)
- ✅ Firefox (78+)
- ✅ Safari (14+)
- ✅ Edge (85+)

## Rest API (Advanced)

If you want to use the dashboard API directly:

```bash
# Get all blocks
curl http://localhost:5000/api/blocks | python -m json.tool

# Get pending transactions
curl http://localhost:5000/api/mempool | python -m json.tool

# Get wallets
curl http://localhost:5000/api/wallets | python -m json.tool

# Get metrics
curl http://localhost:5000/api/metrics | python -m json.tool

# Create transaction
curl -X POST http://localhost:5000/api/create_transaction \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "Alice",
    "receiver": "Bob",
    "amount": 25.0,
    "fee": 0.001
  }'

# Verify chain
curl http://localhost:5000/api/verify_chain | python -m json.tool
```

## Performance Notes

- Dashboard is read-only from blockchain database
- No data corruption risk
- Can safely refresh/restart
- Auto-refresh interval can be adjusted
- All data persists in blockchain.db

## Next Steps

1. **Explore the Dashboard**
   - Click tabs to navigate
   - Try creating transactions
   - View metrics and charts

2. **Modify the System**
   - Edit CSS in `static/style.css` to change colors
   - Modify charts in `static/dashboard.js`
   - Add new endpoints in `dashboard_app/app.py`

3. **Run More Tests**
   - Create multiple transactions
   - Run blockchain system again (creates new blocks)
   - Watch dashboard update in real-time

4. **Integration**
   - See `INTEGRATION_GUIDE.md` for advanced options
   - Share live objects between systems
   - Build custom clients

## Support

For issues:
1. Check terminal output for error messages
2. Review `dashboard_app/README.md` for detailed docs
3. Check `INTEGRATION_GUIDE.md` for advanced setup
4. Verify all dependencies: `pip list | grep -i flask`

## Documentation

- 📖 Full documentation: `dashboard_app/README.md`
- 🔧 Integration guide: `INTEGRATION_GUIDE.md`
- 📝 This quick start: `QUICKSTART.md`

---

**Ready to visualize your blockchain?**

```bash
# Windows: Double-click launch_dashboard.bat
# Or run: cd dashboard_app && python app.py
# Then open: http://localhost:5000
```

🚀 **Launch and enjoy!**
