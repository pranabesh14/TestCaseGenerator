import csv
import json
from pathlib import Path

from code_parser import CodeParser
from code_chunker import CodeChunker
from csv_handler import CSVHandler
from git_handler import GitHandler
from llm_handler import LLMHandler
from source_index import SourceIndex
from test_generator import TestGenerator as Generator


def repository():
    return {
        'include/abc.h': {'code': '''namespace shop {
class Order { public: int run(int x); };
int validate(int x);
}''', 'language': 'cpp'},
        'src/bcd.cpp': {'code': '''#include "abc.h"
namespace shop {
int persist(int x) { return x * 2; }
int validate(int x) { return x >= 0; }
int calculate(int x) { return persist(x); }
int Order::run(int x) {
  if (!validate(x)) return -1;
  return calculate(x);
}
}''', 'language': 'cpp'},
    }


def root_chunk():
    index = SourceIndex(repository())
    root = next(s for s in index.symbols.values() if s['qualified_name'] == 'shop::Order::run')
    return index.workflow(root)[0]


def draft(chunk, **overrides):
    result = {'description': 'Invalid order rejected', 'target': chunk['name'],
              'steps': 'Step 1: Invoke run(-1)\nStep 2: Check the return value',
              'expected_result': 'Returns -1',
              'evidence': [{'symbol_id': chunk['symbol_id'], 'start_line': 7, 'end_line': 7}]}
    result.update(overrides)
    return result


def handler_with_response(response):
    handler = LLMHandler.__new__(LLMHandler)
    handler._make_request = lambda prompt: response
    return handler


def test_implementation_and_all_call_tiers():
    chunk = root_chunk()
    assert chunk['file'] == 'src/bcd.cpp'
    assert len(chunk['direct_calls']) == 2
    assert any('shop::validate' in f for f in chunk['call_tiers'][1])
    assert any('shop::calculate' in f for f in chunk['call_tiers'][1])
    assert any('shop::persist' in f for f in chunk['call_tiers'][2])
    assert chunk['related_files'] == ['include/abc.h', 'src/bcd.cpp']
    assert chunk['context_complete']


def test_cpp_parser_qualified_definitions_comments_and_inline_headers():
    code = '// A comment shifts byte positions but must not shift line numbers.\nint X::run(int x) { return x; }'
    data = CodeParser().parse_code(code, 'src/bcd.cpp')
    assert data['functions'][0]['qualified_name'] == 'X::run'
    assert data['functions'][0]['line'] == 2
    chunks = CodeChunker(10).chunk_code(code, data)
    assert chunks[0]['code'] == 'int X::run(int x) { return x; }'
    idx = SourceIndex({'abc.h': {'code': 'inline int f(int x) { return x; }'}})
    assert next(iter(idx.symbols.values()))['file'] == 'abc.h'


def test_duplicate_paths_static_helpers_and_same_arity_overloads():
    idx = SourceIndex({
        'a/shared.cpp': {'code': 'static int f(int x){return 1;} int a(){return f(1);}'},
        'b/shared.cpp': {'code': 'static int f(int x){return 2;} int b(){return f(1);}'},
        'overloads.cpp': {'code': 'int f(int x){return 1;} int f(double x){return 2;} int c(){return f(1);}'},
    })
    assert len(idx.symbols) == 7
    for symbol in idx.symbols.values():
        if symbol['name'] in {'a', 'b'}:
            edge = idx.edges[symbol['symbol_id']][0]
            assert edge['resolution'] == 'resolved'
            assert idx.symbols[edge['callee']]['file'] == symbol['file']
        elif symbol['name'] == 'c':
            assert idx.edges[symbol['symbol_id']][0]['resolution'] == 'ambiguous'


def test_recursion_and_unknown_member_calls_are_explicit():
    idx = SourceIndex({'code.cpp': {'code': 'int recurse(int x){if(x) return recurse(x-1); return 0;} int run(){return unknown.work();}'}})
    recursive = next(s for s in idx.symbols.values() if s['name'] == 'recurse')
    chunk, _ = idx.workflow(recursive)
    assert len(chunk['call_edges']) == 1
    assert chunk['call_tiers'] == {}
    unknown = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(unknown)
    assert not chunk['context_complete']
    assert any('unknown.work' in w for w in warnings)


def test_budget_never_silently_cuts_function_bodies():
    idx = SourceIndex({'code.cpp': {'code': 'int run(){' + '\nint x=1;' * 500 + '\nreturn 42;}'}})
    root = next(iter(idx.symbols.values()))
    chunk, warnings = idx.workflow(root, max_chars=1500)
    assert chunk is None and 'budget' in warnings[0].lower()
    chunk, warnings = idx.workflow(root, max_chars=60000)
    assert 'return 42;' in chunk['code']
    assert not warnings


def test_python_import_alias_cross_file_calls_and_async():
    idx = SourceIndex({
        'service/api.py': {'code': 'from .helper import validate as check\nasync def run(x):\n    return check(x)\n'},
        'service/helper.py': {'code': 'def validate(x):\n    return persist(x)\ndef persist(x):\n    return x * 2\n'},
    })
    root = next(s for s in idx.symbols.values() if s['qualified_name'] == 'service.api.run')
    chunk, _ = idx.workflow(root)
    assert 'service.helper.validate' in chunk['call_tiers'][1][0]
    assert 'service.helper.persist' in chunk['call_tiers'][2][0]


def test_functional_response_rejects_unknown_targets_and_fabricated_evidence():
    chunk = root_chunk()
    bogus = draft(chunk, evidence=[{'symbol_id': 'invented.cpp:1:fake', 'start_line': 1, 'end_line': 2}])
    bad_line = draft(chunk, evidence=[{'symbol_id': chunk['symbol_id'], 'start_line': 900, 'end_line': 900}])
    response = json.dumps([draft(chunk), bogus, bad_line, draft(chunk, target='fake'),
                           draft(chunk, steps=''), draft(chunk, evidence=[])])
    handler = handler_with_response(response)
    tests = handler.generate_tests_for_chunk(chunk, 'Functional Test', 'incorrect.h')
    assert len(tests) == 1
    assert tests[0]['file'] == 'src/bcd.cpp'
    assert tests[0]['target'] == 'shop::Order::run'
    assert tests[0]['review_status'] == 'Needs Review'
    assert tests[0]['call_tiers'] == chunk['call_tiers']


def test_no_dummy_functional_tests_on_api_or_json_failures():
    chunk = root_chunk()
    for response in ('Error: API quota exceeded', '[invalid json]', '```python\npass\n```', '[]'):
        assert handler_with_response(response).generate_tests_for_chunk(chunk, 'Functional Test') == []


def test_csv_roundtrip_fresh_and_append(tmp_path):
    chunk = root_chunk()
    test = handler_with_response(json.dumps([draft(chunk)])).generate_tests_for_chunk(chunk, 'Functional Test')[0]
    handler = CSVHandler()
    handler.output_dir = tmp_path
    path = handler.generate_csv({'Functional Test': [test]})
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]['Source File'] == 'src/bcd.cpp'
    assert 'shop::persist' in rows[0]['Tiered Functions']
    assert len(json.loads(rows[0]['Direct Calls'])) == 2
    assert rows[0]['Status'] == 'Needs Review'
    # Simulate an old CSV without provenance fields; append must migrate safely.
    old = tmp_path / 'old.csv'
    legacy = {k: v for k, v in rows[0].items() if k not in handler._provenance_columns(test)}
    with old.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(legacy))
        writer.writeheader()
        writer.writerow(legacy)
    new = handler.append_to_previous_csv(old, {'Functional Test': [test]}, {'modified_files': ['src/bcd.cpp']})
    with new.open(newline='') as stream:
        appended = list(csv.DictReader(stream))
    assert len(appended) == 2
    assert json.loads(appended[1]['Call Graph']) == chunk['call_edges']


def test_repository_not_truncated_at_100_files(tmp_path):
    for i in range(120):
        (tmp_path / f'{i}.cpp').write_text('int f(){return 1;}')
    handler = GitHandler()
    assert len(handler.get_code_files(tmp_path)) == 120
    import pytest
    with pytest.raises(ValueError, match='explicit 100-file limit'):
        handler.get_code_files(tmp_path, max_files=100)


def test_module_generation_never_concatenates_or_uses_module_filename():
    class FakeLLM:
        def __init__(self):
            self.chunks = []
        def generate_tests_for_chunk(self, chunk, test_type, filename):
            self.chunks.append(chunk)
            assert filename != 'module'
            assert 'symbol_id' in chunk
            return [{'file': filename, 'target': chunk['name']}]
    llm = FakeLLM()
    generator = Generator(llm, None)
    tests = generator.generate_tests(repository(), ['Functional Test'], module_level=True)['Functional Test']
    assert len(tests) == 4
    assert all(t['file'] == 'src/bcd.cpp' for t in tests)
    root = next(c for c in llm.chunks if c['name'] == 'shop::Order::run')
    assert root['call_tiers'][2]


def test_unsupported_and_invalid_sources_produce_diagnostics():
    idx = SourceIndex({'code.txt': {'code': 'function f() {}'}, 'bad.cpp': {'code': 'int f( { broken'}})
    assert not idx.symbols
    assert len(idx.diagnostics) == 2


def test_header_default_arguments_and_relative_include():
    idx = SourceIndex({
        'include/abc.h': {'code': 'int helper(int x = 5);'},
        'src/bcd.cpp': {'code': '#include "../include/abc.h"\nint helper(int x){return x;} int run(){return helper();}'},
    })
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert idx.edges[root['symbol_id']][0]['resolution'] == 'resolved'
    assert 'include/abc.h' in chunk['related_files']
    assert not warnings


def test_virtual_dispatch_does_not_claim_a_single_runtime_target():
    idx = SourceIndex({'code.cpp': {'code': '''
class Base { public: virtual int work(); };
int Base::work(){return 1;}
int run(Base &b){return b.work();}
'''}})
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    edge = idx.edges[root['symbol_id']][0]
    assert edge['resolution'] == 'dynamic'
    assert edge['callee'] is None


def test_python_nested_function_scope():
    idx = SourceIndex({'code.py': {'code': 'def outer(x):\n    def inner(y):\n        return y * 2\n    return inner(x)\n'}})
    root = next(s for s in idx.symbols.values() if s['qualified_name'] == 'code.outer')
    chunk, warnings = idx.workflow(root)
    assert 'code.outer.inner' in chunk['call_tiers'][1][0]
    assert not warnings


def test_local_callable_is_not_matched_to_global_function():
    idx = SourceIndex({'code.cpp': {'code': 'int helper(){return 1;} int run(){auto helper = [](){return 2;}; return helper();}'}})
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    assert idx.edges[root['symbol_id']][0]['resolution'] == 'unresolved'


def test_standard_csv_and_append_keep_provenance(tmp_path):
    handler = CSVHandler()
    handler.output_dir = tmp_path
    test = {'file': 'src/bcd.cpp', 'target': 'run', 'name': 'test_run', 'code': 'assert run() == 1',
            'call_tiers': {1: ['helper [src/bcd.cpp:1]']}}
    path = handler.generate_csv({'Unit Test': [test]})
    appended = handler.append_to_previous_csv(path, {'Unit Test': [test]}, {})
    with appended.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert all(json.loads(r['Tiered Functions'])['1'][0].startswith('helper') for r in rows)


def test_incomplete_context_and_depth_limit_are_exported():
    idx = SourceIndex(repository())
    root = next(s for s in idx.symbols.values() if s['qualified_name'] == 'shop::Order::run')
    chunk, warnings = idx.workflow(root, max_depth=1)
    assert any('depth' in w.lower() for w in warnings)
    assert not chunk['context_complete']
    assert 2 not in chunk['call_tiers']


def test_malformed_evidence_does_not_abort_valid_scenarios():
    chunk = root_chunk()
    handler = handler_with_response(json.dumps([
        draft(chunk, evidence=[{'symbol_id': {}, 'start_line': 7, 'end_line': 7}]), draft(chunk),
    ]))
    assert len(handler.generate_tests_for_chunk(chunk, 'Functional Test')) == 1
