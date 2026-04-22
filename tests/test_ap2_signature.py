from agent_orchestration.orchestrator.ap2policy import AP2PolicyManager
from agent_orchestration.shared.models import AP2Policy


def test_ap2_signature_verification():
    mgr = AP2PolicyManager(user_secret="0123456789abcdef0123456789abcdef")
    policy = AP2Policy.fresh("data", 0.1, 0.1, ["data.x402.org"])
    signed = mgr._sign(policy)
    assert mgr.verify(signed) is True
    signed.allowed_domains = ["evil.org"]
    assert mgr.verify(signed) is False
