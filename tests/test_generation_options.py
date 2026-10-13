import copy

import pytest

from src.config.database import Database
from src.config.generation import generation_options
from src.managers.task_chain_manager import TaskChainManager


def test_custom_options_keep_integer_seed_and_unknown_provider_ranges():
    draft = {
        "size": "321×199",
        "quality": "provider-specific",
        "n": "3",
        "seed": "-123",
        "negative_prompt": "blur",
        "reference": "unsupported-missing.png",
        "output_format": "unsupported",
        "transparent": True,
    }
    original = copy.deepcopy(draft)
    options = generation_options("custom", "relay-model", draft)
    assert options == {
        "params": {"size": "321x199", "quality": "provider-specific", "n": 3, "seed": -123},
        "negative_prompt": "blur",
        "reference_image_path": None,
    }
    assert draft == original


def test_gpt_image_filters_unsupported_inputs_and_preserves_reference(tmp_path):
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"offline-reference")
    options = generation_options(
        "openai_images",
        "gpt-image-2",
        {
            "size": "1280x768",
            "quality": "high",
            "n": 3,
            "seed": "invalid-but-unsupported",
            "negative_prompt": "unsupported",
            "reference": str(reference),
            "output_format": "webp",
            "transparent": True,
        },
    )
    assert options == {
        "params": {"size": "1280x768", "quality": "high", "n": 3, "output_format": "webp", "background": "transparent"},
        "negative_prompt": "",
        "reference_image_path": str(reference),
    }


@pytest.mark.parametrize(
    "interface_type,model_id,size,quality",
    [
        ("gemini", "gemini-3-pro-image", "16:9", "2K"),
        ("bfl", "flux-2-pro", "768x1024", "auto"),
        ("minimax", "image-01", "3:2", "auto"),
    ],
)
def test_native_options_follow_capabilities(interface_type, model_id, size, quality):
    options = generation_options(interface_type, model_id, {"size": size, "quality": quality, "seed": 0})
    assert options["params"]["size"] == size
    assert options["params"]["quality"] == quality
    assert options["params"]["n"] == 1
    assert ("seed" in options["params"]) == (interface_type != "gemini")


@pytest.mark.parametrize(
    "draft,match",
    [
        ({"size": "0x1024"}, "尺寸"),
        ({"size": "-1x1024"}, "尺寸"),
        ({"size": "1024.5x1024"}, "尺寸"),
        ({"size": "16:9"}, "尺寸"),
        ({"n": 0}, "数量"),
        ({"n": -1}, "数量"),
        ({"n": 1.5}, "数量"),
        ({"n": True}, "数量"),
        ({"seed": "1.5"}, "种子"),
        ({"seed": False}, "种子"),
    ],
)
def test_invalid_supported_numeric_values_are_rejected(draft, match):
    with pytest.raises(ValueError, match=match):
        generation_options("custom", "relay-model", draft)


@pytest.mark.parametrize(
    "interface_type,model_id,draft,match",
    [
        ("gemini", "gemini-3-pro-image", {"size": "1024x1024"}, "画幅"),
        ("gemini", "gemini-3-pro-image", {"quality": "high"}, "质量"),
        ("gemini", "gemini-3-pro-image", {"n": 2}, "一张"),
        ("bfl", "flux-2-pro", {"n": 2}, "一张"),
        ("openai_images", "gpt-image-2", {"transparent": True, "output_format": "jpeg"}, "透明"),
        ("openai_images", "gpt-image-2", {"output_format": "svg"}, "格式"),
    ],
)
def test_provider_options_reject_incompatible_values(interface_type, model_id, draft, match):
    with pytest.raises(ValueError, match=match):
        generation_options(interface_type, model_id, draft)


def test_supported_reference_must_be_an_existing_file(tmp_path):
    for path in (tmp_path, tmp_path / "missing.png"):
        with pytest.raises(ValueError, match="参考图文件不存在"):
            generation_options("openai_images", "gpt-image-2", {"reference": str(path)})


@pytest.mark.parametrize("size", ["240x256", "256x2064", "257x1024"])
def test_flux_size_is_rejected_before_the_adapter_local_failure(size):
    with pytest.raises(ValueError, match="FLUX 尺寸"):
        generation_options("bfl", "flux-2-pro", {"size": size})


def test_flux_size_accepts_existing_adapter_boundaries():
    options = generation_options("bfl", "flux-2-pro", {"size": "256x2048"})
    assert options["params"]["size"] == "256x2048"


def test_minimax_prompt_length_matches_existing_adapter_validation():
    assert generation_options("minimax", "image-01", {"prompt": "图" * 1500})
    with pytest.raises(ValueError, match="1500"):
        generation_options("minimax", "image-01", {"prompt": "图" * 1501})


@pytest.mark.asyncio
async def test_workflow_options_round_trip_and_execute_without_losing_reference(tmp_path):
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"offline-reference")
    tasks = [
        {
            "prompt": "edit a landscape",
            **generation_options("openai_images", "gpt-image-2", {"reference": str(reference), "transparent": True}),
        },
        {
            "prompt": "generate a landscape",
            **generation_options("custom", "relay-model", {"negative_prompt": "blur", "seed": 0, "n": 3}),
        },
    ]

    class CompletingQueue:
        def __init__(self):
            self.tasks = []

        def add_task(self, task):
            self.tasks.append(task)
            task.status = "COMPLETED"
            return str(task.id)

    queue = CompletingQueue()
    db_path = str(tmp_path / "workflow.db")
    db = Database(db_path)
    await db.connect()
    try:
        manager = TaskChainManager(db, queue)
        chain_id = await manager.create_chain({"name": "options", "tasks": tasks})
    finally:
        await db.close()
    restored_db = Database(db_path)
    await restored_db.connect()
    try:
        restored = TaskChainManager(restored_db, queue)
        await restored.load_chains()
        saved = restored.get_chain(chain_id)
        assert saved["tasks"][0]["reference_image_path"] == str(reference)
        assert saved["tasks"][1]["negative_prompt"] == "blur"
        assert saved["tasks"][1]["params"]["seed"] == 0
        await restored.start_chain(chain_id)
        assert len(queue.tasks) == 2
        assert queue.tasks[0].reference_image_path == str(reference)
        assert queue.tasks[0].params["background"] == "transparent"
        assert queue.tasks[1].reference_image_path is None
        assert queue.tasks[1].negative_prompt == "blur"
        assert queue.tasks[1].params["seed"] == 0
        assert queue.tasks[1].params["n"] == 3
    finally:
        await restored_db.close()


def test_legacy_workflow_without_reference_still_loads():
    manager = TaskChainManager(None, None)
    chain = manager._chain_from_data({"tasks": [{"prompt": "legacy"}]}, "legacy")
    assert chain.tasks[0].reference_image_path is None
    assert chain.to_dict()["tasks"][0]["reference_image_path"] is None
