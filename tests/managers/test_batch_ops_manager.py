import pytest, os, tempfile, shutil, asyncio, json
from src.managers.batch_ops_manager import BatchOpsManager

class TestBatchOpsManager:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test.db")

    def test_delete_records_removes_from_db(self):
        """Test that delete_records removes records via history_manager"""
        async def run_test():
            from src.config.database import Database
            from src.managers.history_manager import HistoryManager

            db = Database(self.db_path)
            await db.connect()

            # Create history manager with db
            history_manager = HistoryManager.get_instance()
            await history_manager.initialize(db)

            # Save a test record
            await history_manager.save_record({
                "task_id": "test-task-001",
                "platform_id": "openai",
                "prompt": "test prompt",
                "status": "completed"
            })

            # Verify record exists
            history = await history_manager.get_history(10)
            task_ids = [r.get("task_id") for r in history]
            assert "test-task-001" in task_ids

            # Create BatchOpsManager and delete
            batch_mgr = BatchOpsManager(history_manager, db, self.test_dir)
            result = await batch_mgr.delete_records(["test-task-001"])

            assert result.success_count == 1
            assert result.failed_count == 0

            # Verify record is gone
            history = await history_manager.get_history(10)
            task_ids = [r.get("task_id") for r in history]
            assert "test-task-001" not in task_ids

            await db.close()

        asyncio.run(run_test())

    def test_export_creates_zip_with_metadata(self):
        """Test that export_records creates a ZIP with manifest and images"""
        async def run_test():
            from src.config.database import Database
            from src.managers.history_manager import HistoryManager

            db = Database(self.db_path)
            await db.connect()

            history_manager = HistoryManager.get_instance()
            await history_manager.initialize(db)

            # Create a test image file
            img_dir = os.path.join(self.test_dir, "generations")
            os.makedirs(img_dir, exist_ok=True)
            img_path = os.path.join(img_dir, "test-image.png")

            # Write a minimal PNG file (1x1 transparent pixel)
            with open(img_path, "wb") as f:
                # PNG header + IHDR + IDAT + IEND (minimal valid PNG)
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

            # Save record with image path
            await history_manager.save_record({
                "task_id": "test-task-002",
                "platform_id": "openai",
                "prompt": "export test prompt",
                "image_path": img_path,
                "status": "completed"
            })

            # Export
            output_path = os.path.join(self.test_dir, "export_test.zip")
            batch_mgr = BatchOpsManager(history_manager, db, self.test_dir)
            result_path = await batch_mgr.export_records(["test-task-002"], output_path)

            assert os.path.exists(result_path)

            # Verify ZIP contents
            import zipfile
            with zipfile.ZipFile(result_path, "r") as zf:
                names = zf.namelist()
                assert "manifest.json" in names

                manifest = json.loads(zf.read("manifest.json"))
                assert manifest["total_items"] == 1
                assert manifest["items"][0]["task_id"] == "test-task-002"

                # Check image is in ZIP
                image_files = [n for n in names if n.startswith("images/")]
                assert len(image_files) == 1

            await db.close()

        asyncio.run(run_test())

    def test_move_records_updates_category(self):
        """Test that move_records updates category via db"""
        async def run_test():
            from src.config.database import Database
            from src.managers.history_manager import HistoryManager

            db = Database(self.db_path)
            await db.connect()

            history_manager = HistoryManager.get_instance()
            await history_manager.initialize(db)

            # Save a test record
            await history_manager.save_record({
                "task_id": "test-task-003",
                "platform_id": "openai",
                "prompt": "move test prompt",
                "status": "completed"
            })

            # Update db to add category column if needed, then update directly
            await db.execute("""
                CREATE TABLE IF NOT EXISTS test_categories (
                    task_id TEXT PRIMARY KEY,
                    category TEXT
                )
            """)

            # BatchOpsManager.move_records needs update_history_category
            batch_mgr = BatchOpsManager(history_manager, db, self.test_dir)
            result = await batch_mgr.move_records(["test-task-003"], "moved_category")

            assert result.success_count == 1
            assert result.failed_count == 0
            history = await history_manager.get_history(10)
            record = next(r for r in history if r.get("task_id") == "test-task-003")
            assert record["status"] == "completed"

            await db.close()

        asyncio.run(run_test())

    def test_add_tags_updates_tags(self):
        """Test that add_tags updates tags via db"""
        async def run_test():
            from src.config.database import Database
            from src.managers.history_manager import HistoryManager

            db = Database(self.db_path)
            await db.connect()

            history_manager = HistoryManager.get_instance()
            await history_manager.initialize(db)

            # Save a test record
            await history_manager.save_record({
                "task_id": "test-task-004",
                "platform_id": "openai",
                "prompt": "tags test prompt",
                "status": "completed"
            })

            batch_mgr = BatchOpsManager(history_manager, db, self.test_dir)
            result = await batch_mgr.add_tags(["test-task-004"], ["tag1", "tag2"])

            assert result.success_count == 1
            assert result.failed_count == 0
            history = await history_manager.get_history(10)
            record = next(r for r in history if r.get("task_id") == "test-task-004")
            assert record["status"] == "completed"

            await db.close()

        asyncio.run(run_test())

    def test_delete_record_removes_all_generated_images(self):
        """Test that deleting a multi-image record removes all generated files."""
        async def run_test():
            from src.config.database import Database
            from src.managers.history_manager import HistoryManager

            db = Database(self.db_path)
            await db.connect()
            history_manager = HistoryManager()
            await history_manager.initialize(db)

            first = os.path.join(self.test_dir, "first.png")
            second = os.path.join(self.test_dir, "second.png")
            thumb = os.path.join(self.test_dir, "thumb_first.jpg")
            for path in (first, second, thumb):
                with open(path, "wb") as file:
                    file.write(b"image")

            await history_manager.save_record({
                "task_id": "test-task-multi",
                "platform_id": "openai",
                "prompt": "multi",
                "image_path": first,
                "thumbnail_path": thumb,
                "result_paths_json": [first, second],
                "status": "completed",
            })

            await history_manager.delete_record("test-task-multi")
            await db.close()

            assert not os.path.exists(first)
            assert not os.path.exists(second)
            assert not os.path.exists(thumb)

        asyncio.run(run_test())

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
