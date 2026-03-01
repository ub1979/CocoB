# =============================================================================
# test_sqlite_wal_mode.py — Tests for SQLite WAL mode configuration
# =============================================================================

import pytest
import sqlite3
import tempfile
import os


class TestSQLiteWALMode:
    """Test that SQLite memory uses WAL mode for better concurrency."""

    def test_wal_mode_enabled(self):
        """SQLite database should have WAL mode enabled."""
        from coco_b.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Connect and check journal mode
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute("PRAGMA journal_mode")
                journal_mode = cursor.fetchone()[0]
                assert journal_mode.upper() == "WAL", f"Expected WAL mode, got {journal_mode}"
            finally:
                conn.close()

    def test_synchronous_setting(self):
        """SQLite should have synchronous setting configured."""
        from coco_b.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Connect and check synchronous setting
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute("PRAGMA synchronous")
                synchronous = cursor.fetchone()[0]
                # synchronous=1 is NORMAL mode, 2 is FULL (default)
                # We accept either as long as it's not 0 (OFF)
                assert synchronous in [1, 2], f"Expected synchronous=1 or 2, got {synchronous}"
            finally:
                conn.close()

    def test_tables_created(self):
        """Required tables should be created."""
        from coco_b.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Connect and check tables
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = {row[0] for row in cursor.fetchall()}
                
                assert "facts" in tables, "facts table should exist"
                assert "conversations" in tables, "conversations table should exist"
                assert "facts_fts" in tables, "facts_fts virtual table should exist"
                assert "conversations_fts" in tables, "conversations_fts virtual table should exist"
            finally:
                conn.close()

    def test_wal_file_created(self):
        """WAL mode should create .wal and .shm files during transactions."""
        from coco_b.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Open a connection and start a transaction
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("BEGIN IMMEDIATE")  # Start write transaction
                
                # Check that WAL-related files exist during transaction
                wal_file = db_path + "-wal"
                shm_file = db_path + "-shm"
                
                # At least one of these should exist during write transaction
                assert os.path.exists(wal_file) or os.path.exists(shm_file), \
                    "WAL mode should create .wal or .shm files during transactions"
                
                conn.execute("INSERT INTO facts (user_id, fact, category) VALUES (?, ?, ?)",
                           ("user1", "Test fact", "info"))
                conn.commit()
            finally:
                conn.close()

    def test_concurrent_access(self):
        """WAL mode should allow concurrent reads during writes."""
        from coco_b.core.memory import SQLiteMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_memory.db")
            
            # Create SQLiteMemory instance
            memory = SQLiteMemory(db_path=db_path)
            
            # Add initial data
            memory.add_fact("user1", "Fact 1", "info")
            
            # Open a read connection
            read_conn = sqlite3.connect(db_path)
            try:
                # Start reading
                cursor = read_conn.execute("SELECT * FROM facts")
                rows = cursor.fetchall()
                assert len(rows) == 1
                
                # While reading, write new data (this would block without WAL)
                memory.add_fact("user2", "Fact 2", "info")
                
                # Read again (should see new data)
                cursor = read_conn.execute("SELECT * FROM facts")
                rows = cursor.fetchall()
                assert len(rows) == 2, "WAL mode should allow concurrent reads"
            finally:
                read_conn.close()
