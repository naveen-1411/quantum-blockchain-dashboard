"""
INTEGRATION GUIDE — Running Blockchain + Dashboard Together
=============================================================

This guide shows different ways to run the blockchain system with the web dashboard.

Method 1: Sequential (Simple)
Method 2: Parallel (Intermediate)
Method 3: Integrated (Advanced)
"""

# ══════════════════════════════════════════════════════════════════════════════
# METHOD 1: SEQUENTIAL EXECUTION (SIMPLEST)
# ══════════════════════════════════════════════════════════════════════════════

"""
Run blockchain system first, then start dashboard in a separate terminal.

Terminal 1:
    python main_v2.py

Wait for main_v2.py to complete (usually 10-20 seconds).
The blockchain data is saved to blockchain.db and metrics.db.

Terminal 2:
    cd dashboard_app
    python app.py

Then open browser: http://localhost:5000
"""

# ══════════════════════════════════════════════════════════════════════════════
# METHOD 2: PARALLEL EXECUTION (BETTER FOR DEMOS)
# ══════════════════════════════════════════════════════════════════════════════

"""
Run both systems simultaneously. The dashboard can read the database
while blockchain is still running.

Terminal 1:
    python main_v2.py

Terminal 2 (while terminal 1 is still running):
    cd dashboard_app
    python app.py

Then open browser: http://localhost:5000

ADVANTAGE: Dashboard shows real-time updates as new transactions/blocks are added.
DISADVANTAGE: Requires two terminals.
"""

# ══════════════════════════════════════════════════════════════════════════════
# METHOD 3: INTEGRATED EXECUTION (ADVANCED)
# ══════════════════════════════════════════════════════════════════════════════

"""
Optionally modify main_v2.py to share live blockchain objects with dashboard.

Add to main_v2.py (before the banner or at the very end):
```
# Import dashboard sharing function (optional)
try:
    from dashboard_app.app import set_shared_objects
    set_shared_objects(chain, network, wallets, metrics, wallet_registry)
    print("[INTEGRATION] Dashboard objects shared")
except ImportError:
    print("[INFO] Dashboard not available (install Flask and run dashboard)")
```

Then, in a separate terminal while main_v2.py is running:
    cd dashboard_app
    python app.py

The dashboard will have access to live blockchain objects, not just database files.
"""

# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDED WORKFLOW FOR DEMONSTRATIONS
# ══════════════════════════════════════════════════════════════════════════════

"""
1. Install dashboard dependencies:
   pip install -r dashboard_app/requirements.txt

2. Terminal 1 - Run blockchain demo:
   python main_v2.py
   
   This will:
   ✓ Create wallets
   ✓ Initialize nodes and network
   ✓ Create transactions
   ✓ Mine blocks with PoW
   ✓ Run PBFT consensus
   ✓ Verify chain integrity
   ✓ Run adversarial tests
   ✓ Benchmark cryptographic operations
   ✓ Save to blockchain.db and metrics.db

3. Terminal 2 - Run dashboard (while Terminal 1 is running or after):
   cd dashboard_app
   python app.py
   
   Output:
   ============================================================
     QUANTUM-RESISTANT BLOCKCHAIN — WEB DASHBOARD
   ============================================================
   
     Starting Flask server on http://localhost:5000
     Press CTRL+C to stop

4. Open Web Browser:
   Navigate to: http://localhost:5000
   
   You should see:
   - Blockchain Explorer with all blocks
   - Transactions (confirmed and pending)
   - Wallet balances
   - Network nodes
   - Performance metrics with charts
   - Tools for chain verification

5. Interact with Dashboard:
   - View blocks and transactions
   - Create new transactions (form in Transactions tab)
   - Verify blockchain integrity
   - Check performance metrics
   - Monitor mempool for pending transactions
   - Auto-refresh is enabled by default
"""

# ══════════════════════════════════════════════════════════════════════════════
# TROUBLESHOOTING
# ══════════════════════════════════════════════════════════════════════════════

"""
Issue: "Flask not found" when running dashboard
Solution: pip install Flask

Issue: "Port 5000 already in use"
Solution: Kill existing process or change port in dashboard_app/app.py line 567

Issue: "No blocks showing in dashboard"
Solution: Make sure blockchain.db exists. Run main_v2.py first.

Issue: "Metrics tab is empty"
Solution: Metrics are populated during the benchmark section of main_v2.py.
         If it ran too quickly, may need to wait or run manual benchmarks.

Issue: "Transaction creation fails"
Solution: Make sure you have wallets and sufficient balance selected.
         Check browser console for error details.
"""

# ══════════════════════════════════════════════════════════════════════════════
# FEATURES VERIFICATION CHECKLIST
# ══════════════════════════════════════════════════════════════════════════════

"""
After starting the dashboard, verify these features work:

Blockchain Explorer:
  ☐ All blocks displayed with headers
  ☐ Click block to see transaction details
  ☐ Genesis block shown as #0
  ☐ Hash values visible

Transaction Monitor:
  ☐ Confirmed transactions listed
  ☐ Mempool shows pending transactions
  ☐ Transaction creation form works
  ☐ New transactions appear in mempool

Wallets:
  ☐ All wallets displayed (Alice, Bob, Validators)
  ☐ Balances shown correctly
  ☐ Wallet addresses visible

Nodes:
  ☐ Network nodes listed
  ☐ Roles (sender/receiver/validator) shown
  ☐ Status displayed

Metrics:
  ☐ Charts render for key generation, encryption, signatures
  ☐ Detailed metrics table populated
  ☐ Statistics (mean, median, p95) visible

Tools:
  ☐ "Verify Chain" button works
  ☐ Chain verification report shows
  ☐ Chain statistics displayed
  ☐ Auto-refresh toggle works
"""

# ══════════════════════════════════════════════════════════════════════════════
# AUTOMATED LAUNCHER SCRIPT
# ══════════════════════════════════════════════════════════════════════════════

"""
To create an automated launcher, create 'run_all.py' in the project root:

```python
import subprocess
import time
import sys
import webbrowser
from pathlib import Path

scripts = [
    ("Blockchain System", "main_v2.py", False),
    ("Dashboard Server", "dashboard_app/app.py", True),
]

processes = []

print("\\n" + "="*60)
print("  QUANTUM-RESISTANT BLOCKCHAIN + DASHBOARD")
print("="*60 + "\\n")

for name, script, is_background in scripts:
    print(f"Starting {name}...")
    p = subprocess.Popen(
        [sys.executable, script],
        cwd=Path(__file__).parent
    )
    processes.append((name, p))
    
    if not is_background:
        # Wait for output
        time.sleep(10)
    else:
        # Quick wait then open browser
        time.sleep(3)
        print(f"✓ {name} started")

print("\\nOpening dashboard in browser...")
time.sleep(2)
webbrowser.open("http://localhost:5000")

print("\\nBoth systems running!")
print("Dashboard: http://localhost:5000")
print("Press CTRL+C to stop all services\\n")

try:
    for name, p in processes:
        p.wait()
except KeyboardInterrupt:
    print("\\nShutting down...")
    for name, p in processes:
        p.terminate()
    for name, p in processes:
        p.wait()
    print("All services stopped.")
```

Then run:
    python run_all.py
"""

print(__doc__)
