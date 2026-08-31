"""文档 ACL（访问控制列表）的纯策略测试。"""

from __future__ import annotations

import unittest

from rag_agent_demo.contracts import UserIdentity
from rag_agent_demo.vector_store import is_authorized_payload


class PermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        # 测试用户属于 demo 租户和 engineering 群组。
        self.engineer = UserIdentity(user_id="u-1", tenant_id="demo", groups=["engineering"])

    def test_same_tenant_and_overlapping_group_is_allowed(self) -> None:
        # 同租户且群组有交集，才允许进入候选集。
        payload = {"tenant_id": "demo", "allowed_groups": ["engineering", "security"]}
        self.assertTrue(is_authorized_payload(payload, self.engineer))

    def test_different_tenant_is_denied_even_when_group_matches(self) -> None:
        # 群组相同不能绕过租户隔离。
        payload = {"tenant_id": "other", "allowed_groups": ["engineering"]}
        self.assertFalse(is_authorized_payload(payload, self.engineer))

    def test_non_overlapping_group_is_denied(self) -> None:
        # 同租户也必须有至少一个允许群组。
        payload = {"tenant_id": "demo", "allowed_groups": ["support"]}
        self.assertFalse(is_authorized_payload(payload, self.engineer))


if __name__ == "__main__":
    unittest.main()
