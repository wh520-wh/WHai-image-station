from src.config import constants


def test_constants_are_human_readable_and_not_mojibake():
    assert constants.TASK_STATUS["WAITING"] == "等待中"
    assert constants.PLATFORM_DEFAULTS["openai"]["name"] == "DALL·E / OpenAI Compatible"
    assert constants.QUALITY_OPTIONS["openai"] == ["标准", "HD"]
    assert len(constants.SIZE_OPTIONS["openai"]) == len({item[0] for item in constants.SIZE_OPTIONS["openai"]})
