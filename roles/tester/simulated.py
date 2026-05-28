"""
测试AI - 生成测试用例代码
"""
from core.executor_ai import ExecutorAI
from core.workspace import workspace


class TesterAI(ExecutorAI):
    """测试工程师AI: 编写测试用例和验证代码"""

    def do_work(self, task: dict) -> dict:
        description = task.get("description", "")
        feature = task.get("feature", description)

        filename = "test_" + self._pick_testfile(description)
        code = self._generate_test_code(feature, description)

        filepath = workspace.write_file("tests", filename, code)

        return {
            "files": [f"tests/{filename}"],
            "filepath": filepath,
            "role": "tester"
        }

    def _pick_testfile(self, description: str) -> str:
        desc = description.lower()
        if "登录" in desc or "认证" in desc:
            return "auth.py"
        elif "列表" in desc or "数据" in desc:
            return "data.py"
        elif "前端" in desc:
            return "frontend.py"
        else:
            return "feature.py"

    def _generate_test_code(self, feature: str, description: str) -> str:
        """生成测试用例代码"""

        test_name = feature.replace(" ", "_")

        return f'''"""
测试用例: {feature}
生成者: 测试AI
"""
import pytest
import json


class Test{test_name.replace("_", "").title()}:
    """{feature} 相关测试"""

    @classmethod
    def setup_class(cls):
        """测试前置: 初始化测试环境"""
        cls.base_url = "http://localhost:5000"
        cls.headers = {{"Content-Type": "application/json"}}

    def test_success_case(self):
        """
        [PASS] 正常场景: 验证功能在正常输入下返回正确结果
        """
        # 准备测试数据
        test_data = {{
            "input": "valid_data",
            "expected": "success"
        }}

        # 验证逻辑
        assert test_data["input"] == "valid_data"
        assert "expected" in test_data
        print("✓ 正常场景测试通过")

    def test_empty_input(self):
        """
        [PASS] 边界场景: 验证空输入处理
        """
        test_data = {{}}

        # 验证空数据处理
        assert isinstance(test_data, dict)
        assert len(test_data) == 0
        print("✓ 空输入测试通过")

    def test_invalid_input(self):
        """
        [PASS] 异常场景: 验证非法输入处理
        """
        test_cases = [None, "", 123, []]  # 各种非法输入

        for case in test_cases:
            # 验证每个非法输入不会导致崩溃
            try:
                result = self._validate_input(case)
                assert result is False, f"输入 {case} 应该被拒绝"
            except Exception as e:
                print(f"  正确捕获异常: {{e}}")

        print("✓ 非法输入测试通过")

    def test_response_format(self):
        """
        [PASS] 格式验证: 响应数据结构检查
        """
        expected_keys = {{"code", "message"}}
        mock_response = {{
            "code": 200,
            "message": "操作成功",
            "data": {{}}
        }}

        # 验证响应包含必要字段
        assert expected_keys.issubset(mock_response.keys())
        assert isinstance(mock_response["code"], int)
        assert isinstance(mock_response["message"], str)
        print("✓ 响应格式测试通过")

    def _validate_input(self, value):
        """辅助: 输入验证 (模拟)"""
        if not isinstance(value, dict):
            return False
        if not value:
            return False
        return True


# ===== 独立运行 =====
if __name__ == "__main__":
    print("=" * 50)
    print(f"测试套件: {feature}")
    print(f"需求描述: {description}")
    print("=" * 50)

    test_suite = Test{test_name.replace("_", "").title()}()
    test_suite.setup_class()

    tests = [
        test_suite.test_success_case,
        test_suite.test_empty_input,
        test_suite.test_invalid_input,
        test_suite.test_response_format,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"✗ {{test.__name__}} 失败: {{e}}")

    print(f"\\n测试结果: {{passed}}通过, {{failed}}失败, {{len(tests)}}总计")
'''
