from app.services.analysis_parser import build_analysis_artifacts, build_patent_prompt


def test_prompt_warns_against_novelty_assertions():
    prompt = build_patent_prompt("装置/设备")

    assert "不要断言" in prompt
    assert "具有新颖性" in prompt
    assert "待人工确认" in prompt


def test_prompt_includes_user_context_as_input_material():
    prompt = build_patent_prompt("装置/设备", "权利要求1：一种带有传感器的检测设备。")

    assert "用户提供的确定性上下文" in prompt
    assert "权利要求1：一种带有传感器的检测设备。" in prompt
    assert "图片与上下文不一致或待人工确认" in prompt


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
    assert artifacts["structured_result"]["image_context"]["technical_domain"] == "未知"
    assert "展示机械结构的技术图纸" in artifacts["structured_result"]["image_context"]["visible_evidence"]


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


def test_build_artifacts_preserves_image_context_fields():
    raw_output = {
        "image_type": "结构示意图",
        "scene_context": "用于说明设备内部模块装配关系",
        "technical_domain": "智能制造设备",
        "visible_evidence": ["图中可见主体壳体", "传感器与控制模块相连"],
        "context_alignment": "图片与权利要求中的检测设备基本对应",
        "context_supported_points": ["图片支持传感器与控制模块连接"],
        "context_gaps": ["图片无法确认传感器型号"],
        "inferred_context": ["可能用于自动化检测流程"],
        "uncertainties": ["无法确认传感器型号"],
        "content_description": "设备主体内设置传感器和控制模块",
        "technical_features": ["传感器连接控制模块"],
    }

    artifacts = build_analysis_artifacts(raw_output, "apparatus", "权利要求1：一种检测设备。")
    context = artifacts["structured_result"]["image_context"]
    context_analysis = artifacts["structured_result"]["context_analysis"]

    assert artifacts["structured_result"]["user_context"] == "权利要求1：一种检测设备。"
    assert context["scene"] == "用于说明设备内部模块装配关系"
    assert context["image_type"] == "结构示意图"
    assert context["technical_domain"] == "智能制造设备"
    assert context["visible_evidence"] == ["图中可见主体壳体", "传感器与控制模块相连"]
    assert context_analysis["alignment"] == "图片与权利要求中的检测设备基本对应"
    assert context_analysis["supported_points"] == ["图片支持传感器与控制模块连接"]
    assert context_analysis["gaps"] == ["图片无法确认传感器型号"]
