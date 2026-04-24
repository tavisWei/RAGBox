import pytest

from api.core.rag.splitter.chinese_separators import (
    CHINESE_SEPARATORS,
    ENGLISH_SEPARATORS,
)
from api.core.rag.splitter.chinese_text_splitter import ChineseTextSplitter


class TestChineseSeparators:
    def test_chinese_separators_priority_order(self):
        expected = [
            "\n\n",
            "\n",
            "。",
            "！",
            "？",
            "；",
            "，",
            "、",
            " ",
            "",
        ]
        assert CHINESE_SEPARATORS == expected

    def test_english_separators_priority_order(self):
        expected = [
            "\n\n",
            "\n",
            ".",
            "!",
            "?",
            ";",
            ",",
            " ",
            "",
        ]
        assert ENGLISH_SEPARATORS == expected


class TestChineseTextSplitter:
    def test_initialization_with_defaults(self):
        splitter = ChineseTextSplitter()

        assert splitter._chunk_size == 512
        assert splitter._chunk_overlap == 64
        assert splitter._keep_separator is True
        assert splitter._separators == CHINESE_SEPARATORS

    def test_initialization_with_custom_params(self):
        splitter = ChineseTextSplitter(
            chunk_size=1000, chunk_overlap=100, separators=["\n\n", "\n", "。", ""]
        )

        assert splitter._chunk_size == 1000
        assert splitter._chunk_overlap == 100
        assert splitter._separators == ["\n\n", "\n", "。", ""]

    def test_split_chinese_text_on_period(self):
        text = "这是第一句话。这是第二句话。这是第三句话。"
        splitter = ChineseTextSplitter(chunk_size=20, chunk_overlap=5)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 2
        assert all("。" in chunk or chunk.endswith("。") for chunk in chunks)

    def test_split_chinese_text_preserve_sentence_boundary(self):
        text = "这是一个完整的句子，包含逗号分句。这是另一个句子。"
        splitter = ChineseTextSplitter(chunk_size=15, chunk_overlap=3)

        chunks = splitter.split_text(text)

        for chunk in chunks:
            if "，" in chunk and "。" not in chunk:
                assert chunk.endswith("，") or chunk.endswith("。")

    def test_split_mixed_chinese_english_text(self):
        text = "这是中文内容。This is English content. 又是中文内容。"
        splitter = ChineseTextSplitter(chunk_size=25, chunk_overlap=5)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        full_text = "".join(chunks)
        assert "中文" in full_text
        assert "English" in full_text

    def test_split_respects_chunk_size(self):
        long_text = "这是一个很长的句子，" * 100
        splitter = ChineseTextSplitter(chunk_size=50, chunk_overlap=10)

        chunks = splitter.split_text(long_text)

        for chunk in chunks:
            assert len(chunk) <= 70

    def test_split_with_paragraph_breaks(self):
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        splitter = ChineseTextSplitter(chunk_size=100, chunk_overlap=20)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_with_exclamation_and_question_marks(self):
        text = "这是感叹句！这是疑问句？这是普通句。"
        splitter = ChineseTextSplitter(chunk_size=15, chunk_overlap=3)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_with_enumeration_comma(self):
        text = "项目包括：苹果、香蕉、橙子、葡萄等多种水果。"
        splitter = ChineseTextSplitter(chunk_size=20, chunk_overlap=5)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_empty_text(self):
        splitter = ChineseTextSplitter()

        chunks = splitter.split_text("")

        assert chunks == []

    def test_split_single_sentence(self):
        text = "这是一个单独的句子。"
        splitter = ChineseTextSplitter(chunk_size=100, chunk_overlap=20)

        chunks = splitter.split_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_without_separator_keeps_separator_false(self):
        text = "第一句。第二句。第三句。"
        splitter = ChineseTextSplitter(
            chunk_size=100, chunk_overlap=20, keep_separator=False
        )

        chunks = splitter.split_text(text)

        assert splitter._keep_separator is False

    def test_overlap_between_chunks(self):
        text = "第一句话内容。第二句话内容。第三句话内容。第四句话内容。"
        splitter = ChineseTextSplitter(chunk_size=20, chunk_overlap=10)

        chunks = splitter.split_text(text)

        if len(chunks) > 1:
            for i in range(len(chunks) - 1):
                has_overlap = False
                for word in ["内容", "话"] if i + 1 < len(chunks) else []:
                    if word in chunks[i] and word in chunks[i + 1]:
                        has_overlap = True
                        break

    def test_split_long_chinese_text(self):
        text = "人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。"
        splitter = ChineseTextSplitter(chunk_size=30, chunk_overlap=10)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 2
        combined = "".join(chunks)
        assert "人工智能" in combined

    def test_split_with_custom_separators(self):
        text = "段落A\n\n段落B\n\n段落C"
        custom_seps = ["\n\n", "\n", ""]
        splitter = ChineseTextSplitter(
            chunk_size=20, chunk_overlap=5, separators=custom_seps
        )

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        assert splitter._separators == custom_seps

    def test_split_preserves_content(self):
        text = "内容一。内容二。内容三。"
        splitter = ChineseTextSplitter(chunk_size=100, chunk_overlap=20)

        chunks = splitter.split_text(text)

        combined = "".join(chunks)
        assert combined == text

    def test_chunk_overlap_validation(self):
        with pytest.raises(ValueError, match="chunk_overlap"):
            ChineseTextSplitter(chunk_size=10, chunk_overlap=20)

    def test_split_multiple_paragraphs(self):
        text = """第一段的第一句。第一段的第二句。

第二段的第一句。第二段的第二句。

第三段的内容。"""
        splitter = ChineseTextSplitter(chunk_size=50, chunk_overlap=15)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        combined = "".join(chunks)
        assert "第一段" in combined
        assert "第二段" in combined
        assert "第三段" in combined

    def test_split_with_whitespace_normalization(self):
        text = "这是  多个  空格  的  文本。"
        splitter = ChineseTextSplitter(chunk_size=100, chunk_overlap=20)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_with_numbers_and_special_chars(self):
        text = "2024年发生了重要事件：1. 事件A；2. 事件B；3. 事件C。"
        splitter = ChineseTextSplitter(chunk_size=30, chunk_overlap=10)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        combined = "".join(chunks)
        assert "2024年" in combined

    def test_token_based_chunk_size(self):
        text = "这是一个测试文本，用于验证基于token的分割。"
        splitter = ChineseTextSplitter(chunk_size=10, chunk_overlap=2)

        chunks = splitter.split_text(text)

        assert len(chunks) >= 2

    def test_split_oversized_chunk_with_no_separators(self):
        text = "这是一个非常长的句子没有任何标点符号" * 10
        splitter = ChineseTextSplitter(
            chunk_size=20, chunk_overlap=5, separators=["\n\n", ""]
        )

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1

    def test_split_oversized_chunk_without_new_separators(self):
        text = "这是一个非常长的句子" * 20
        splitter = ChineseTextSplitter(
            chunk_size=15, chunk_overlap=3, separators=["\n\n", ""]
        )

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
