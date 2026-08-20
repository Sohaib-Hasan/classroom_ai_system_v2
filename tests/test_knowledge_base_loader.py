from unittest.mock import MagicMock, patch

import pytest

from knowledge_base_loader import ensure_knowledge_base_present, needs_download


class TestNeedsDownload:
    def test_missing_file_needs_download(self, tmp_path):
        path = tmp_path / "knowledge_base.json"  # kabhi banayi hi nahi
        assert needs_download(str(path)) is True

    def test_lfs_pointer_sized_file_needs_download(self, tmp_path):
        path = tmp_path / "knowledge_base.json"
        path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 111008937\n")
        assert needs_download(str(path)) is True

    def test_valid_large_file_does_not_need_download(self, tmp_path):
        path = tmp_path / "knowledge_base.json"
        path.write_bytes(b"x" * 2_000_000)  # 2MB — well above threshold
        assert needs_download(str(path)) is False


class TestEnsureKnowledgeBasePresent:
    """FIX (Aug 2026, deployment bug): GitHub LFS free-tier bandwidth
    quota khatam hone par, GitHub silently sirf ek chhota "pointer"
    text file serve karta hai asli 111MB content ki jagah — matlab app
    locally chalti thi (asli file disk par thi) lekin Streamlit Cloud
    par crash hoti thi. Ye tests confirm karte hain ke loader ab is
    scenario ko detect kar ke GitHub Release se real file download
    karta hai, aur valid file ko chhedta nahi."""

    def test_valid_large_file_is_left_alone(self, tmp_path):
        path = tmp_path / "knowledge_base.json"
        path.write_bytes(b"x" * 2_000_000)

        with patch("requests.get") as mock_get:
            ensure_knowledge_base_present(str(path))
            assert not mock_get.called, "Valid file should never trigger a download"

    def test_lfs_pointer_sized_file_triggers_download(self, tmp_path, monkeypatch):
        import knowledge_base_loader

        monkeypatch.setattr(
            knowledge_base_loader, "KNOWLEDGE_BASE_URL",
            "https://github.com/fake/repo/releases/download/v1/knowledge_base.json",
        )
        path = tmp_path / "knowledge_base.json"
        path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 111008937\n")

        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.iter_content.return_value = [b'{"real": "downloaded content"}']

        with patch("requests.get", return_value=fake_resp) as mock_get:
            ensure_knowledge_base_present(str(path))
            assert mock_get.called

        assert path.read_bytes() == b'{"real": "downloaded content"}'

    def test_missing_file_triggers_download(self, tmp_path, monkeypatch):
        import knowledge_base_loader

        monkeypatch.setattr(
            knowledge_base_loader, "KNOWLEDGE_BASE_URL",
            "https://github.com/fake/repo/releases/download/v1/knowledge_base.json",
        )
        path = tmp_path / "knowledge_base.json"  # kabhi banayi hi nahi

        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.iter_content.return_value = [b"downloaded"]

        with patch("requests.get", return_value=fake_resp) as mock_get:
            ensure_knowledge_base_present(str(path))
            assert mock_get.called
        assert path.exists()

    def test_placeholder_url_raises_clear_error_not_a_silent_crash(self, tmp_path, monkeypatch):
        # Agar koi placeholder URL bhool jaye replace karna, error clear
        # honi chahiye ("URL configure karein"), na ke koi confusing
        # network/JSON error jo asal wajah chhupaye
        import knowledge_base_loader

        monkeypatch.setattr(
            knowledge_base_loader, "KNOWLEDGE_BASE_URL",
            "https://github.com/x/y/releases/download/REPLACE_WITH_YOUR_TAG/knowledge_base.json",
        )
        path = tmp_path / "knowledge_base.json"
        path.write_text("version https://git-lfs.github.com/spec/v1\n")

        with pytest.raises(RuntimeError, match="KNOWLEDGE_BASE_URL"):
            ensure_knowledge_base_present(str(path))

    def test_download_is_atomic_no_temp_file_left_behind(self, tmp_path, monkeypatch):
        # Agar download beech mein crash ho jaye, poori purani (invalid)
        # file bhi na bache aur na hi ek adhoori (corrupt) file save ho —
        # os.replace() ka use isi liye hai (atomic rename)
        import knowledge_base_loader

        monkeypatch.setattr(
            knowledge_base_loader, "KNOWLEDGE_BASE_URL",
            "https://github.com/fake/repo/releases/download/v1/knowledge_base.json",
        )
        path = tmp_path / "knowledge_base.json"
        path.write_text("version https://git-lfs.github.com/spec/v1\n")

        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.iter_content.return_value = [b"chunk1", b"chunk2"]

        with patch("requests.get", return_value=fake_resp):
            ensure_knowledge_base_present(str(path))

        assert not (tmp_path / "knowledge_base.json.downloading").exists()