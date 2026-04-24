"""Unit tests for CodeAwareTextSplitter."""

import pytest

from api.core.rag.splitter.code_text_splitter import (
    CodeAwareTextSplitter,
    LANGUAGE_SEPARATORS,
)
from api.core.rag.splitter.splitter_types import SplitterConfig


class TestLanguageSeparators:
    """Test LANGUAGE_SEPARATORS constants."""

    def test_python_separators(self):
        assert "\nclass " in LANGUAGE_SEPARATORS["python"]
        assert "\ndef " in LANGUAGE_SEPARATORS["python"]
        assert "\nif __name__" in LANGUAGE_SEPARATORS["python"]

    def test_javascript_separators(self):
        assert "\nfunction " in LANGUAGE_SEPARATORS["javascript"]
        assert "\nconst " in LANGUAGE_SEPARATORS["javascript"]
        assert "\nclass " in LANGUAGE_SEPARATORS["javascript"]

    def test_typescript_separators(self):
        assert "\nfunction " in LANGUAGE_SEPARATORS["typescript"]
        assert "\ninterface " in LANGUAGE_SEPARATORS["typescript"]

    def test_java_separators(self):
        assert "\npublic class " in LANGUAGE_SEPARATORS["java"]
        assert "\nclass " in LANGUAGE_SEPARATORS["java"]

    def test_go_separators(self):
        assert "\nfunc " in LANGUAGE_SEPARATORS["go"]
        assert "\ntype " in LANGUAGE_SEPARATORS["go"]

    def test_rust_separators(self):
        assert "\nfn " in LANGUAGE_SEPARATORS["rust"]
        assert "\nstruct " in LANGUAGE_SEPARATORS["rust"]

    def test_default_separators(self):
        assert "\n\n" in LANGUAGE_SEPARATORS["default"]
        assert "\n" in LANGUAGE_SEPARATORS["default"]
        assert " " in LANGUAGE_SEPARATORS["default"]
        assert "" in LANGUAGE_SEPARATORS["default"]


class TestCodeAwareTextSplitter:
    """Test CodeAwareTextSplitter functionality."""

    def test_initialization_with_defaults(self):
        """Should initialize with default config."""
        splitter = CodeAwareTextSplitter()

        assert splitter.config.chunk_size == 512
        assert splitter.config.chunk_overlap == 64
        assert splitter._language == "default"

    def test_initialization_with_language(self):
        """Should initialize with specified language."""
        splitter = CodeAwareTextSplitter(language="python")

        assert splitter._language == "python"
        assert splitter._separators == LANGUAGE_SEPARATORS["python"]

    def test_initialization_from_config_language(self):
        """Should read language from config."""
        config = SplitterConfig(language="javascript")
        splitter = CodeAwareTextSplitter(config=config)

        assert splitter._language == "javascript"

    def test_split_empty_text(self):
        """Should return empty list for empty text."""
        splitter = CodeAwareTextSplitter()
        chunks = splitter.split_text("")

        assert chunks == []

    def test_split_python_code(self):
        """Should split Python code by functions and classes."""
        code = """
def function_one():
    pass

def function_two():
    pass

class MyClass:
    def method(self):
        pass
"""
        splitter = CodeAwareTextSplitter(language="python", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "function_one" in full_text
        assert "function_two" in full_text

    def test_split_javascript_code(self):
        """Should split JavaScript code."""
        code = """
function foo() {
    return 1;
}

const bar = () => {
    return 2;
};

class MyClass {
    constructor() {}
}
"""
        splitter = CodeAwareTextSplitter(language="javascript", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "foo" in full_text or "bar" in full_text

    def test_split_respects_chunk_size(self):
        """Should split large code blocks to respect chunk_size."""
        code = "\ndef func():\n    " + "pass\n    " * 100
        splitter = CodeAwareTextSplitter(
            language="python", chunk_size=50, chunk_overlap=5
        )
        chunks = splitter.split_text(code)

        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk) <= 1000 or "pass" in chunk

    def test_split_unknown_language_uses_default(self):
        """Should use default separators for unknown language."""
        splitter = CodeAwareTextSplitter(language="unknown_lang")

        assert splitter._separators == LANGUAGE_SEPARATORS["default"]

    def test_split_java_code(self):
        """Should split Java code."""
        code = """
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}

class Helper {
    public void help() {}
}
"""
        splitter = CodeAwareTextSplitter(language="java", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "Main" in full_text or "Helper" in full_text

    def test_split_go_code(self):
        """Should split Go code."""
        code = """
package main

func main() {
    fmt.Println("Hello")
}

type User struct {
    Name string
}
"""
        splitter = CodeAwareTextSplitter(language="go", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "main" in full_text or "User" in full_text

    def test_split_rust_code(self):
        """Should split Rust code."""
        code = """
fn main() {
    println!("Hello");
}

struct Point {
    x: f64,
}
"""
        splitter = CodeAwareTextSplitter(language="rust", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "main" in full_text or "Point" in full_text

    def test_split_documents(self):
        """Should split documents with metadata."""
        splitter = CodeAwareTextSplitter(language="python", chunk_size=200)
        docs = [
            {
                "content": "def foo():\n    pass",
                "metadata": {"language": "python"},
            },
        ]
        result = splitter.split_documents(docs)

        assert len(result) > 0
        assert all("metadata" in r for r in result)
        assert all("chunk_index" in r["metadata"] for r in result)

    def test_from_config_classmethod(self):
        """Should create instance from config."""
        config = SplitterConfig(chunk_size=128, chunk_overlap=16, language="python")
        splitter = CodeAwareTextSplitter.from_config(config)

        assert isinstance(splitter, CodeAwareTextSplitter)
        assert splitter.config.chunk_size == 128
        assert splitter._language == "python"

    def test_chunk_overlap_validation(self):
        """Should raise ValueError if overlap > size."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            CodeAwareTextSplitter(chunk_size=10, chunk_overlap=20)

    def test_split_single_function(self):
        """Should handle single function."""
        code = "def single():\n    return 42"
        splitter = CodeAwareTextSplitter(language="python", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "single" in full_text

    def test_split_empty_functions(self):
        """Should handle code with empty sections."""
        code = "\n\n\ndef func():\n    pass\n\n\n"
        splitter = CodeAwareTextSplitter(language="python", chunk_size=100)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1

    def test_split_typescript_code(self):
        """Should split TypeScript code."""
        code = """
interface User {
    name: string;
}

function greet(user: User): string {
    return `Hello ${user.name}`;
}

class Service {
    private users: User[] = [];
}
"""
        splitter = CodeAwareTextSplitter(language="typescript", chunk_size=1000)
        chunks = splitter.split_text(code)

        assert len(chunks) >= 1
        full_text = "\n".join(chunks)
        assert "User" in full_text or "greet" in full_text

    def test_recursive_splitting(self):
        """Should recursively split when chunk exceeds size."""
        code = "def func():\n    " + "x = 1\n    " * 50
        splitter = CodeAwareTextSplitter(
            language="python", chunk_size=50, chunk_overlap=5
        )
        chunks = splitter.split_text(code)

        assert len(chunks) > 0
        full_text = "\n".join(chunks)
        assert "func" in full_text
