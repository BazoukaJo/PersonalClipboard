from personalclipboard.asr.cuda_runtime import configure_cuda12_dlls


def test_configure_cuda12_dlls_is_safe() -> None:
    dirs = configure_cuda12_dlls()
    assert isinstance(dirs, list)
