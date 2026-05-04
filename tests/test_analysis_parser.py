from app.services.analysis_parser import build_analysis_artifacts, build_patent_prompt


def test_prompt_warns_against_novelty_assertions():
    prompt = build_patent_prompt("装置/设备")

    assert "不要断言" in prompt
    assert "具有新颖性" in prompt
    assert "待人工确认" in prompt


def test_build_artifacts_handles_legacy_mock_dict():
    raw_output = {
        "image_type": "技术图纸",
        "main_content": "展示机械结构的技术图纸",
        "technical_features": ["包含多个机械部件的连接关系"],
        "key_elements": ["主体框架"],
        "patent_suggestions": "建议从结构创新和连接方式角度撰写",
    }

    artifacts = build_analysis_artifacts(raw_output, "apparatus")

    assert artifacts["technical_description"] == "展示机械结构的技术图纸"
    assert artifacts["key_features"] == ["包含多个机械部件的连接关系"]
    assert artifacts["patent_elements"]["claim_type"] == "apparatus"
    assert "待确认事项" in artifacts["novelty_analysis"]


def test_build_artifacts_does_not_fake_novelty_when_json_is_invalid():
    artifacts = build_analysis_artifacts("not json at all", "general")

    assert "当前图片不足以直接判断新颖性" in artifacts["novelty_analysis"]
    assert "结构设计具有独创性" not in artifacts["novelty_analysis"]
    assert "需人工复核" in artifacts["novelty_analysis"]


def test_build_artifacts_labels_potential_points_as_search_required():
    raw_output = """
    ```json
    {
      "content_description": "一种带有可调支架的设备",
      "technical_features": ["可调支架连接主体"],
      "novelty_points": ["可调支架与主体的一体化连接"]
    }
    ```
    """

    artifacts = build_analysis_artifacts(raw_output, "apparatus")

    assert "可调支架与主体的一体化连接" in artifacts["novelty_analysis"]
    assert "需通过现有技术检索确认" in artifacts["novelty_analysis"]
