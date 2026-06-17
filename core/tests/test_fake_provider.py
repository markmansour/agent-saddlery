import pytest

from saddlery.llm.fake import FakeProvider
from saddlery.messages import Message


async def test_fake_provider_yields_text_deltas():
    provider = FakeProvider(["Hel", "lo"])
    out = [d.text async for d in provider.stream([Message(role="user", content="hi")], model="x")]
    assert out == ["Hel", "lo"]


async def test_fake_provider_raises_after_chunks():
    provider = FakeProvider(["a"], error=RuntimeError("boom"))
    collected = []
    with pytest.raises(RuntimeError, match="boom"):
        async for delta in provider.stream([], model="x"):
            collected.append(delta.text)
    assert collected == ["a"]
