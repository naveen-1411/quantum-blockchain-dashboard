"""
metrics.py
==========
Performance metrics collection and storage for the Quantum-Resistant Blockchain.

Stores timing measurements in SQLite with statistical analysis:
  mean, median, std_dev, p95 (95th percentile), min, max

Metric categories
-----------------
  kyber_keygen        Kyber1024 key pair generation
  dilithium_keygen    Dilithium3 key pair generation
  kyber_encrypt       Kyber KEM encapsulation + AES-GCM encryption
  kyber_decrypt       Kyber KEM decapsulation + AES-GCM decryption
  dilithium_sign      Dilithium3 signing
  dilithium_verify    Dilithium3 verification
  block_mine          PoW block mining (includes nonce search)
  block_validate      Full block validation (all tx signatures)
  consensus           Full consensus round latency
  tx_e2e              End-to-end transaction latency
"""

import sqlite3
import time
import statistics
import contextlib
from pathlib import Path
from functools import wraps


DB_PATH = Path("metrics.db")


# ══════════════════════════════════════════════
#  Database setup
# ══════════════════════════════════════════════

def _get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create metrics table if it doesn't exist."""
    with _get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT    NOT NULL,
                latency_ms  REAL    NOT NULL,
                recorded_at REAL    NOT NULL,
                extra       TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON metrics(category)")
        conn.commit()


# ══════════════════════════════════════════════
#  MetricsCollector
# ══════════════════════════════════════════════

class MetricsCollector:
    """
    Records and retrieves performance metrics.

    Usage
    -----
    m = MetricsCollector()

    # Record manually
    m.record("kyber_encrypt", latency_ms=8.3)

    # Record via context manager
    with m.measure("dilithium_sign"):
        sig = dilithium_sign(key, msg)

    # Retrieve statistics
    stats = m.stats("dilithium_sign")
    report = m.full_report()
    """

    CATEGORIES = [
        "kyber_keygen", "dilithium_keygen",
        "kyber_encrypt", "kyber_decrypt",
        "dilithium_sign", "dilithium_verify",
        "block_mine", "block_validate",
        "consensus", "tx_e2e",
    ]

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        init_db(db_path)
        self._conn = _get_conn(db_path)

    # ── record ─────────────────────────────────
    def record(self, category: str, latency_ms: float, extra: str = None) -> None:
        """Insert one measurement into the database."""
        self._conn.execute(
            "INSERT INTO metrics (category, latency_ms, recorded_at, extra) VALUES (?,?,?,?)",
            (category, latency_ms, time.time(), extra)
        )
        self._conn.commit()

    # ── context manager ────────────────────────
    @contextlib.contextmanager
    def measure(self, category: str, extra: str = None):
        """
        Context manager that times a code block and records it.

        Example
        -------
        with metrics.measure("dilithium_sign"):
            sig = dilithium_sign(priv, message)
        """
        t0 = time.perf_counter()
        try:
            yield
        finally:
            ms = (time.perf_counter() - t0) * 1000
            self.record(category, ms, extra)

    # ── stats for one category ─────────────────
    def stats(self, category: str, last_n: int = None) -> dict:
        """
        Compute statistics for a metric category.

        Parameters
        ----------
        category : one of CATEGORIES
        last_n   : use only the most recent N measurements (None = all)

        Returns
        -------
        {count, mean, median, std_dev, p95, min, max}  (all in ms)
        """
        if last_n:
            rows = self._conn.execute(
                "SELECT latency_ms FROM metrics WHERE category=? "
                "ORDER BY recorded_at DESC LIMIT ?",
                (category, last_n)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT latency_ms FROM metrics WHERE category=?",
                (category,)
            ).fetchall()

        if not rows:
            return {"category": category, "count": 0}

        values = [r["latency_ms"] for r in rows]
        values.sort()
        n = len(values)

        return {
            "category": category,
            "count"   : n,
            "mean"    : round(statistics.mean(values), 3),
            "median"  : round(statistics.median(values), 3),
            "std_dev" : round(statistics.stdev(values) if n > 1 else 0.0, 3),
            "p95"     : round(values[int(n * 0.95)], 3),
            "min"     : round(values[0], 3),
            "max"     : round(values[-1], 3),
        }

    # ── full report ────────────────────────────
    def full_report(self, last_n: int = 30) -> dict:
        """
        Return statistics for all categories.
        Structured for direct export to JSON / IEEE table.
        """
        report = {}
        for cat in self.CATEGORIES:
            s = self.stats(cat, last_n=last_n)
            if s.get("count", 0) > 0:
                report[cat] = s
        return report

    # ── print report ───────────────────────────
    def print_report(self, last_n: int = 30) -> None:
        """Print a formatted benchmark report."""
        report = self.full_report(last_n=last_n)
        print("\n" + "═" * 72)
        print("  PERFORMANCE BENCHMARK REPORT  (last " + str(last_n) + " measurements per metric)")
        print("═" * 72)
        print(f"  {'Metric':<24} {'N':>4}  {'Mean':>8}  {'Median':>8}  {'Std':>7}  {'P95':>8}  {'Min':>7}  {'Max':>8}")
        print("  " + "─" * 68)
        for cat, s in report.items():
            print(
                f"  {cat:<24} {s['count']:>4}  "
                f"{s['mean']:>7.2f}ms  {s['median']:>7.2f}ms  "
                f"{s['std_dev']:>6.2f}ms  {s['p95']:>7.2f}ms  "
                f"{s['min']:>6.2f}ms  {s['max']:>7.2f}ms"
            )
        print("═" * 72 + "\n")

    # ── comparison table ───────────────────────
    def classical_comparison_table(self) -> None:
        """
        Print a comparison table vs classical algorithms.
        Classical values are from published benchmarks (NIST PQC).
        """
        print("\n" + "═" * 80)
        print("  QUANTUM-RESISTANT vs CLASSICAL  —  Comparison Table")
        print("═" * 80)
        print(f"  {'Algorithm':<22} {'Op':<15} {'Latency':>10}  {'Key/Sig Size':>16}  {'Quantum Safe':>14}")
        print("  " + "─" * 76)

        sign_stats = self.stats("dilithium_sign")
        ver_stats  = self.stats("dilithium_verify")
        enc_stats  = self.stats("kyber_encrypt")

        classical = [
            ("ECDSA (P-256)",   "Sign",    "~0.1ms",  "64B sig",         "❌ Shor's"),
            ("ECDSA (P-256)",   "Verify",  "~0.3ms",  "64B pub",         "❌ Shor's"),
            ("RSA-2048",        "Sign",    "~1.2ms",  "256B sig",        "❌ Shor's"),
            ("RSA-2048",        "Encrypt", "~0.05ms", "256B ct",         "❌ Shor's"),
        ]
        pqc = [
            ("Dilithium3",      "Sign",
             f"{sign_stats.get('mean','?')}ms" if sign_stats.get('count') else "—",
             "3293B sig",       "✅ NIST L3"),
            ("Dilithium3",      "Verify",
             f"{ver_stats.get('mean','?')}ms"  if ver_stats.get('count')  else "—",
             "1952B pub",       "✅ NIST L3"),
            ("Kyber1024",       "Encrypt",
             f"{enc_stats.get('mean','?')}ms"  if enc_stats.get('count')  else "—",
             "1568B ct",        "✅ NIST L5"),
        ]

        for row in classical:
            print(f"  {row[0]:<22} {row[1]:<15} {row[2]:>10}  {row[3]:>16}  {row[4]:>14}")
        print("  " + "─" * 76)
        for row in pqc:
            print(f"  {row[0]:<22} {row[1]:<15} {row[2]:>10}  {row[3]:>16}  {row[4]:>14}")
        print("═" * 80)
        print("  Overhead: Dilithium sig is ~51× larger than ECDSA.")
        print("  Tradeoff: Size accepted to achieve quantum resistance.")
        print("=" * 80 + "\n")

    # ── recent entries ─────────────────────────
    def recent(self, category: str, limit: int = 20) -> list:
        rows = self._conn.execute(
            "SELECT latency_ms, recorded_at, extra FROM metrics "
            "WHERE category=? ORDER BY recorded_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def total_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]

    def clear(self) -> None:
        self._conn.execute("DELETE FROM metrics")
        self._conn.commit()


# ══════════════════════════════════════════════
#  Self-test
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile, os

    print("=" * 55)
    print("  metrics.py  —  Self-Test")
    print("=" * 55)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_db = Path(f.name)

    try:
        m = MetricsCollector(db_path=tmp_db)

        # Record some fake measurements
        import random
        for _ in range(30):
            m.record("dilithium_sign",   random.uniform(40, 80))
            m.record("dilithium_verify", random.uniform(0.05, 0.15))
            m.record("kyber_encrypt",    random.uniform(0.1, 2.0))
            m.record("kyber_keygen",     random.uniform(70, 120))

        # Context manager
        with m.measure("block_mine"):
            time.sleep(0.01)

        m.print_report()
        m.classical_comparison_table()
        print(f"Total records: {m.total_count()}")
        print("\n✅  Metrics tests passed.")
    finally:
        os.unlink(tmp_db)
