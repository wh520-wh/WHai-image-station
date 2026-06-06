import pytest
import tempfile
import os
import asyncio
from src.config.database import Database


class TestDatabaseMigration:
    """Test database migration functionality"""

    def test_task_chains_table_created(self):
        """Test that task_chains table exists after migration"""
        async def run_test():
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name

            try:
                db = Database(db_path)
                await db.connect()

                # Check that _migrate_to_v2 method exists
                assert hasattr(db, '_migrate_to_v2'), "Database should have _migrate_to_v2 method"

                # Run migration
                await db._migrate_to_v2()

                # Verify task_chains table exists
                cursor = await db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='task_chains'"
                )
                row = await cursor.fetchone()
                assert row is not None, "task_chains table should exist after _migrate_to_v2"

                # Verify table structure
                cursor = await db._conn.execute("PRAGMA table_info(task_chains)")
                columns = {col[1] for col in await cursor.fetchall()}
                required_columns = {'id', 'name', 'created_at', 'status', 'failure_mode', 'tasks_json'}
                assert required_columns.issubset(columns), f"task_chains should have columns {required_columns}"

                await db.close()
            finally:
                try:
                    os.unlink(db_path)
                except Exception:
                    pass

        asyncio.run(run_test())

    def test_migration_v2_adds_tags_column(self):
        """Test that migration v2 adds tags column to history table"""
        async def run_test():
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name

            try:
                db = Database(db_path)
                await db.connect()

                # Check that _migrate_to_v2 method exists
                assert hasattr(db, '_migrate_to_v2'), "Database should have _migrate_to_v2 method"

                # Run migration
                await db._migrate_to_v2()

                # Verify tags column exists in generation_history
                cursor = await db._conn.execute("PRAGMA table_info(generation_history)")
                columns = {col[1] for col in await cursor.fetchall()}
                assert 'tags' in columns, "generation_history should have tags column after _migrate_to_v2"

                await db.close()
            finally:
                try:
                    os.unlink(db_path)
                except Exception:
                    pass

        asyncio.run(run_test())

    def test_migration_v3_stub_exists(self):
        """Test that migration v3 stub exists for future key encryption"""
        async def run_test():
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
                db_path = f.name

            try:
                db = Database(db_path)
                await db.connect()

                # Check that _migrate_to_v3 method exists
                assert hasattr(db, '_migrate_to_v3'), "Database should have _migrate_to_v3 method"
                # Method should exist but can be a pass/stub for now
                await db._migrate_to_v3()

                await db.close()
            finally:
                try:
                    os.unlink(db_path)
                except Exception:
                    pass

        asyncio.run(run_test())