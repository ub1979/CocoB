# =============================================================================
# test_sqlite_timeout.py — Tests for SQLite connection timeout
# =============================================================================

import pytest
import sqlite3
import tempfile
import os
import threading
import time


class TestSQLiteTimeout:
    """Test SQLite connection timeout configuration."""

    def test_connection_uses_timeout(self):
        """SQLite connection should use 30 second timeout."""
        from skillforge.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Get a connection and check timeout
            conn = memory._connect()
            try:
                # SQLite doesn't expose timeout directly, but we can verify
                # the connection works and has the expected properties
                cursor = conn.execute("PRAGMA busy_timeout")
                busy_timeout = cursor.fetchone()[0]
                # busy_timeout is in milliseconds, should be 30000 (30 seconds)
                assert busy_timeout == 30000, f"Expected busy_timeout=30000ms, got {busy_timeout}"
            finally:
                conn.close()

    def test_connection_handles_concurrent_access(self):
        """Connection timeout should allow handling concurrent access."""
        from skillforge.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Add initial data
            memory.add_fact("user1", "Fact 1", "info")
            
            results = []
            
            def writer():
                """Thread that writes to database."""
                try:
                    for i in range(5):
                        memory.add_fact(f"user{i}", f"Fact {i}", "info")
                        time.sleep(0.01)
                    results.append("writer_success")
                except Exception as e:
                    results.append(f"writer_failed: {e}")
            
            def reader():
                """Thread that reads from database."""
                try:
                    for i in range(5):
                        facts = memory.get_user_facts("user1")
                        time.sleep(0.01)
                    results.append("reader_success")
                except Exception as e:
                    results.append(f"reader_failed: {e}")
            
            # Run writer and reader concurrently
            writer_thread = threading.Thread(target=writer)
            reader_thread = threading.Thread(target=reader)
            
            writer_thread.start()
            reader_thread.start()
            
            writer_thread.join()
            reader_thread.join()
            
            # Both should succeed without "database is locked" errors
            assert "writer_success" in results, f"Writer should succeed: {results}"
            assert "reader_success" in results, f"Reader should succeed: {results}"

    def test_connection_has_row_factory(self):
        """Connection should have row_factory set to sqlite3.Row."""
        from skillforge.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Get a connection
            conn = memory._connect()
            try:
                assert conn.row_factory == sqlite3.Row, \
                    "Connection should have row_factory set to sqlite3.Row"
            finally:
                conn.close()

    def test_multiple_connections_can_coexist(self):
        """Multiple connections should be able to coexist."""
        from skillforge.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Open multiple connections
            conn1 = memory._connect()
            conn2 = memory._connect()
            conn3 = memory._connect()
            
            try:
                # All should be valid connections
                for i, conn in enumerate([conn1, conn2, conn3], 1):
                    cursor = conn.execute("SELECT 1")
                    result = cursor.fetchone()[0]
                    assert result == 1, f"Connection {i} should work"
            finally:
                conn1.close()
                conn2.close()
                conn3.close()
