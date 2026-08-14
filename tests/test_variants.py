from personalclipboard.llm.variants import MAX_VARIANTS, PhraseBank


def test_record_keeps_original_and_selects_rewrite() -> None:
    bank = PhraseBank()
    bank.reset("Hello there.")
    assert bank.record("Hello there.") == "Hello there."
    assert bank.record("Hi there.") == "Hi there."
    assert bank.items == ["Hello there.", "Hi there."]
    assert bank.index == 1


def test_step_wraps_to_original_then_asks_for_retry() -> None:
    bank = PhraseBank()
    bank.reset("Hello there.")
    bank.record("Hi there.")
    assert bank.step() == "Hello there."
    assert bank.step() == "Hi there."
    assert bank.step() is None
    original, temperature, seed = bank.begin_retry()
    assert original == "Hello there."
    assert temperature >= 0.55
    assert seed > 0
    assert bank.retrying is True
    assert bank.record("Hey there.") == "Hey there."
    assert bank.retrying is False
    assert "Hey there." in bank.items


def test_duplicate_correction_does_not_grow_list() -> None:
    bank = PhraseBank()
    bank.reset("Same.")
    bank.record("Same.")
    assert bank.items == ["Same."]
    assert bank.step() is None


def test_step_wraps_at_cap() -> None:
    bank = PhraseBank()
    bank.reset("v0")
    for index in range(1, MAX_VARIANTS):
        bank.record(f"v{index}")
    assert len(bank.items) == MAX_VARIANTS
    assert bank.step() == "v0"
