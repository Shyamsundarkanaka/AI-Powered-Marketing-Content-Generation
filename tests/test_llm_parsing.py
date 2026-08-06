"""Tests for the response parser in graph/llm.py.

These cover the shapes a model actually returns in the wild. Every case here
was a real failure mode of the previous `find("{") … rfind("}")` implementation
or of a plain `json.loads`.
"""
from __future__ import annotations

import pytest

from graph.llm import SchemaError, extract_json, response_text


class TestExtractJson:
    def test_bare_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_fence(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_unlabelled_fence(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_leading_prose(self):
        assert extract_json('Sure, here you go:\n\n{"a": 1}') == {"a": 1}

    def test_trailing_prose_containing_a_brace(self):
        # rfind("}") would have swallowed the prose and produced invalid JSON.
        raw = '{"a": 1}\n\nLet me know if you want me to adjust {anything}!'
        assert extract_json(raw) == {"a": 1}

    def test_two_objects_takes_the_first(self):
        assert extract_json('{"a": 1}\n{"b": 2}') == {"a": 1}

    def test_trailing_commas(self):
        assert extract_json('{"a": [1, 2,], "b": 3,}') == {"a": [1, 2], "b": 3}

    def test_line_and_block_comments(self):
        raw = '{\n  // the objective\n  "a": 1 /* inline */,\n  "b": 2\n}'
        assert extract_json(raw) == {"a": 1, "b": 2}

    def test_double_slash_inside_a_string_is_not_a_comment(self):
        assert extract_json('{"url": "https://example.com/x"}') == {"url": "https://example.com/x"}

    def test_smart_quotes_used_as_delimiters(self):
        assert extract_json("{“a”: “b”}") == {"a": "b"}

    def test_smart_quotes_used_as_content_are_preserved(self):
        # The quote-straightening pass is destructive, so it must only run when
        # the document is otherwise unparseable — never on valid copy that
        # happens to contain typographic quotes.
        raw = '{"caption": "the “best” board"}'
        assert extract_json(raw) == {"caption": "the “best” board"}

    def test_apostrophe_inside_a_string_survives(self):
        assert extract_json('{"a": "it\'s fine"}') == {"a": "it's fine"}

    def test_single_element_array_is_unwrapped(self):
        assert extract_json('[{"a": 1}]') == {"a": 1}

    def test_nested_braces_and_escaped_quotes(self):
        raw = '{"a": {"b": "he said \\"hi\\" {ok}"}, "c": [{"d": 1}]}'
        assert extract_json(raw) == {"a": {"b": 'he said "hi" {ok}'}, "c": [{"d": 1}]}

    def test_newlines_inside_strings(self):
        # strict=False is what allows a raw newline inside a JSON string, which
        # models emit constantly in multi-paragraph captions.
        assert extract_json('{"a": "line one\nline two"}') == {"a": "line one\nline two"}

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "I'm sorry, I can't help with that.", "{", '{"a": ', "null", "[1, 2]"],
    )
    def test_unusable_responses_raise_schema_error(self, raw):
        with pytest.raises(SchemaError):
            extract_json(raw)

    def test_error_message_is_actionable(self):
        with pytest.raises(SchemaError, match="single JSON object"):
            extract_json("I cannot do that")


class TestResponseText:
    def test_plain_string(self):
        assert response_text("hello") == "hello"

    def test_content_blocks_keep_only_text(self):
        blocks = [
            {"type": "thinking", "thinking": "let me reason about this {"},
            {"type": "text", "text": '{"a": 1}'},
        ]
        assert response_text(blocks) == '{"a": 1}'

    def test_empty_content(self):
        assert response_text(None) == ""

    def test_reasoning_only_response_yields_no_json(self):
        blocks = [{"type": "thinking", "thinking": "hmm"}]
        with pytest.raises(SchemaError):
            extract_json(response_text(blocks))
