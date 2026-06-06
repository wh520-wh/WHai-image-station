import pytest

from src.models.task_chain import ChainTask, TaskChain

def test_chain_task_default_trigger():
    task = ChainTask(task_id="t1", chain_order=0, prompt="test")
    assert task.trigger_on == "success"

def test_task_chain_default_status():
    chain = TaskChain(name="Test Chain", tasks=[])
    assert chain.status == "idle"

def test_task_chain_to_dict():
    chain = TaskChain(name="Test", tasks=[])
    d = chain.to_dict()
    assert d["name"] == "Test"
    assert d["status"] == "idle"