"""Per-language parsing, workflow generation and CSV provenance fixtures."""
import csv
import json

import pytest

from csv_handler import CSVHandler
from source_index import SourceIndex
from llm_handler import LLMHandler
from test_generator import TestGenerator as Generator


CASES = {
    'js': 'function leaf(x){return x*2;} const helper = (x) => leaf(x); function run(x){return helper(x);}',
    'jsx': 'function leaf(x){return x*2;} function helper(x){return leaf(x);} function run(x){return helper(x);} function View(){return <span/>;}',
    'ts': 'function leaf(x:number){return x*2;} class S { helper(x:number){return leaf(x);} run(x:number){return this.helper(x);} }',
    'tsx': 'function leaf(x:number){return x*2;} function helper(x:number){return leaf(x);} function run(x:number){return helper(x);} function View(){return <span/>;}',
    'java': 'package demo; class S { static int leaf(int x){return x*2;} private int helper(int x){return leaf(x);} int run(int x){return helper(x);} }',
    'cs': 'namespace Demo; class S { static int leaf(int x)=>x*2; int helper(int x){return leaf(x);} int run(int x){return helper(x);} }',
    'go': 'package demo\nfunc leaf(x int) int {return x*2}\nfunc helper(x int) int {return leaf(x)}\nfunc run(x int) int {return helper(x)}\n',
    'rs': 'fn leaf(x:i32)->i32{x*2} fn helper(x:i32)->i32{leaf(x)} fn run(x:i32)->i32{helper(x)}',
    'rb': 'module Demo\nclass S\ndef leaf(x)\nx*2\nend\ndef helper(x)\nleaf(x)\nend\ndef run(x)\nhelper(x)\nend\nend\nend\n',
    'php': '<?php namespace Demo; function leaf($x){return $x*2;} class S { function helper($x){return leaf($x);} function run($x){return $this->helper($x);} }',
    'swift': 'func leaf(_ x: Int) -> Int { return x * 2 }\nclass S { func helper(_ x: Int) -> Int { return leaf(x) }\nfunc run(_ x: Int) -> Int { return helper(x) } }\n',
    'kt': 'package demo\nfun leaf(x: Int): Int = x * 2\nclass S {\nfun helper(x: Int): Int = leaf(x)\nfun run(x: Int): Int = helper(x)\n}\n',
    'kts': 'fun leaf(x: Int): Int = x * 2\nfun helper(x: Int): Int = leaf(x)\nfun run(x: Int): Int = helper(x)\n',
    'scala': 'package demo\nobject S { def leaf(x:Int):Int = x*2\ndef helper(x:Int):Int = leaf(x)\ndef run(x:Int):Int = helper(x) }\n',
    'r': 'leaf <- function(x) { x*2 }\nhelper <- function(x) { leaf(x) }\nrun <- function(x) { helper(x) }\n',
    'm': 'function y=leaf(x)\ny=x*2;\nend\nfunction y=helper(x)\ny=leaf(x);\nend\nfunction y=run(x)\ny=helper(x);\nend\n',
}


@pytest.mark.parametrize('extension', CASES)
def test_each_language_preserves_definitions_and_call_tiers(extension):
    filename = 'src/code.' + extension
    idx = SourceIndex({filename: {'code': CASES[extension]}})
    assert not idx.diagnostics
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert chunk['file'] == filename
    assert 'helper' in chunk['call_tiers'][1][0]
    assert 'leaf' in chunk['call_tiers'][2][0]
    assert chunk['line_end'] >= chunk['line_start']
    assert root['code'] in '\n'.join(line.split(': ', 1)[-1] for line in chunk['code'].splitlines())


@pytest.mark.parametrize('extension', CASES)
def test_functional_generation_and_csv_for_each_language(extension, tmp_path):
    filename = 'src/code.' + extension
    handler = LLMHandler.__new__(LLMHandler)
    captured = []
    class FixtureLLM:
        def generate_tests_for_chunk(self, chunk, test_type, file_name):
            captured.append(chunk)
            draft = {'description': 'Fixture scenario', 'target': chunk['name'],
                     'steps': 'Invoke the function with fixture inputs',
                     'expected_result': 'Review the implemented return value',
                     'evidence': [{'symbol_id': chunk['symbol_id'], 'start_line': chunk['line_start'], 'end_line': chunk['line_end']}]}
            handler._make_request = lambda prompt: json.dumps([draft])
            return handler.generate_tests_for_chunk(chunk, test_type, file_name)
    generator = Generator(FixtureLLM(), None)
    tests = generator.generate_tests({filename: {'code': CASES[extension]}}, ['Functional Test'], True)
    assert not generator.diagnostics
    assert tests['Functional Test']
    csv_handler = CSVHandler()
    csv_handler.output_dir = tmp_path
    output = csv_handler.generate_csv(tests)
    with output.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    root = next(r for r in rows if r['Target Function/Class'] == 'run' or r['Target Function/Class'].endswith('.run'))
    assert root['Source File'] == filename
    assert 'leaf' in root['Tiered Functions']
    assert json.loads(root['Source Evidence'])


def test_javascript_alias_import_cross_file_and_namespace_import():
    idx = SourceIndex({
        'src/api.js': {'code': "import { helper as check } from './helpers.js'; export function run(x){return check(x);}"},
        'src/helpers.js': {'code': "import * as storage from './storage.js'; export function helper(x){return storage.leaf(x);}"},
        'src/storage.js': {'code': 'export function leaf(x){return x*2;}'},
    })
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert 'src/helpers.js' in chunk['call_tiers'][1][0]
    assert 'src/storage.js' in chunk['call_tiers'][2][0]


@pytest.mark.parametrize('extension,files', [
    ('java', {'api.java': 'package demo; class API { static int run(int x){return Helpers.helper(x);} }',
              'helper.java': 'package demo; class Helpers { static int helper(int x){return leaf(x);} static int leaf(int x){return x*2;} }'}),
    ('cs', {'api.cs': 'namespace Demo; class API { static int run(int x){return Helpers.helper(x);} }',
            'helper.cs': 'namespace Demo; class Helpers { static int helper(int x){return leaf(x);} static int leaf(int x){return x*2;} }'}),
    ('go', {'api.go': 'package demo\nfunc run(x int) int { return helper(x) }\n',
            'helper.go': 'package demo\nfunc helper(x int) int { return leaf(x) }\nfunc leaf(x int) int {return x*2}\n'}),
    ('rs', {'lib.rs': 'mod helper; fn run(x:i32)->i32{crate::helper::helper(x)}',
            'helper.rs': 'pub fn helper(x:i32)->i32{leaf(x)} fn leaf(x:i32)->i32{x*2}'}),
    ('kt', {'api.kt': 'package demo\nfun run(x: Int): Int = helper(x)\n',
            'helper.kt': 'package demo\nfun helper(x: Int): Int = leaf(x)\nfun leaf(x: Int): Int = x * 2\n'}),
    ('scala', {'api.scala': 'package demo\nobject API { def run(x:Int):Int = Helpers.helper(x) }\n',
               'helper.scala': 'package demo\nobject Helpers { def helper(x:Int):Int = leaf(x)\ndef leaf(x:Int):Int = x*2 }\n'}),
    ('swift', {'api.swift': 'func run(_ x: Int) -> Int { return helper(x) }\n',
               'helper.swift': 'func helper(_ x: Int) -> Int { return leaf(x) }\nfunc leaf(_ x: Int) -> Int { return x * 2 }\n'}),
    ('rb', {'api.rb': 'module Demo\ndef run(x)\nhelper(x)\nend\nend\n',
            'helper.rb': 'module Demo\ndef helper(x)\nleaf(x)\nend\ndef leaf(x)\nx*2\nend\nend\n'}),
    ('php', {'api.php': '<?php namespace Demo; function run($x){return helper($x);}',
             'helper.php': '<?php namespace Demo; function helper($x){return leaf($x);} function leaf($x){return $x*2;}'}),
    ('r', {'api.r': 'run <- function(x) { helper(x) }\n',
           'helper.r': 'helper <- function(x) { leaf(x) }\nleaf <- function(x) { x*2 }\n'}),
    ('m', {'run.m': 'function y=run(x)\ny=helper(x);\nend\n',
           'helper.m': 'function y=helper(x)\ny=leaf(x);\nend\nfunction y=leaf(x)\ny=x*2;\nend\n'}),
])
def test_cross_file_workflows(extension, files):
    idx = SourceIndex({'src/' + name: {'code': code} for name, code in files.items()})
    assert not idx.diagnostics
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert 'helper' in chunk['call_tiers'][1][0]
    assert 'leaf' in chunk['call_tiers'][2][0]
    assert len(chunk['related_files']) == 2


def test_default_javascript_export_and_commonjs_export_object():
    idx = SourceIndex({
        'src/api.js': {'code': "import check from './helper.js'; export function run(x){return check(x);}"},
        'src/helper.js': {'code': "import {leaf} from './storage.js'; export default function helper(x){return leaf(x);}"},
        'src/storage.js': {'code': 'function leaf(x){return x*2;} module.exports={leaf};'},
    })
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert 'src/helper.js' in chunk['call_tiers'][1][0]
    assert 'src/storage.js' in chunk['call_tiers'][2][0]


def test_commonjs_require_alias_and_exported_anonymous_function():
    idx = SourceIndex({
        'api.js': {'code': "const {helper:check}=require('./helper'); function run(x){return check(x);}"},
        'helper.js': {'code': 'function leaf(x){return x*2;} exports.helper=function(x){return leaf(x);};'},
    })
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert chunk['call_tiers'][2]


def test_typescript_imported_class_static_method():
    idx = SourceIndex({
        'api.ts': {'code': "import {Helpers} from './helper'; function run(x:number){return Helpers.helper(x);}"},
        'helper.ts': {'code': 'export class Helpers { static helper(x:number){return x*2;} }'},
    })
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert 'helper.ts' in chunk['call_tiers'][1][0]


def test_java_overload_and_virtual_candidates_remain_visible():
    idx = SourceIndex({'api.java': {'code': '''
class API {
 static int helper(int x){return 1;}
 static int helper(double x){return 2;}
 int work(int x){return x;}
 static int run(int x){return helper(x);}
 int call(int x){return this.work(x);}
}'''}})
    roots = {s['name']: s for s in idx.symbols.values() if s['name'] in {'run', 'call'}}
    overloaded = idx.edges[roots['run']['symbol_id']][0]
    assert overloaded['resolution'] == 'ambiguous'
    assert len(overloaded['candidate_definitions']) == 2
    virtual = idx.edges[roots['call']['symbol_id']][0]
    assert virtual['resolution'] == 'dynamic'
    assert virtual['candidate_definitions'][0]['file'] == 'api.java'


@pytest.mark.parametrize('extension,code', [
    ('js', 'function helper(x){return x;} function run(helper){return helper(1);}'),
    ('ts', 'function helper(x:number){return x;} function run(helper:(x:number)=>number){return helper(1);}'),
    ('go', 'package demo\nfunc helper(x int) int{return x}\nfunc run(helper func(int) int) int{return helper(1)}\n'),
    ('rs', 'fn helper(x:i32)->i32{x} fn run(helper:fn(i32)->i32)->i32{helper(1)}'),
    ('r', 'helper <- function(x){x}\nrun <- function(helper){helper(1)}\n'),
])
def test_callback_parameter_not_misresolved_to_repository_function(extension, code):
    idx = SourceIndex({'code.' + extension: {'code': code}})
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    assert idx.edges[root['symbol_id']][0]['resolution'] == 'unresolved'


def test_go_grouped_parameters_and_import_alias():
    idx = SourceIndex({
        'api/api.go': {'code': 'package api\nimport svc "example/service"\nfunc run(x,y int) int{return svc.Helper(x,y)}\n'},
        'service/helper.go': {'code': 'package service\nfunc Helper(x,y int) int{return x+y}\n'},
    })
    root = next(s for s in idx.symbols.values() if s['name'] == 'run')
    chunk, warnings = idx.workflow(root)
    assert not warnings
    assert 'service/helper.go' in chunk['call_tiers'][1][0]


def test_kotlin_alias_and_rust_use_alias():
    for files in [
        {'api.kt': 'package demo\nimport other.helper as check\nfun run(x: Int): Int = check(x)\n',
         'helper.kt': 'package other\nfun helper(x: Int): Int = x * 2\n'},
        {'src/lib.rs': 'mod helper; use crate::helper::helper as check; fn run(x:i32)->i32{check(x)}',
         'src/helper.rs': 'pub fn helper(x:i32)->i32{x*2}'},
    ]:
        idx = SourceIndex({name: {'code': code} for name, code in files.items()})
        root = next(s for s in idx.symbols.values() if s['name'] == 'run')
        chunk, warnings = idx.workflow(root)
        assert not warnings
        assert chunk['call_tiers'][1]


def test_all_extensions_available_for_parser_upload_and_repository_discovery(tmp_path):
    from code_parser import CodeParser
    from code_chunker import CodeChunker
    from git_handler import GitHandler
    from config import config
    from language_adapters import EXTENSION_LANGUAGES
    assert set(EXTENSION_LANGUAGES) <= set(config.SUPPORTED_EXTENSIONS)
    git_handler = GitHandler()
    assert set(EXTENSION_LANGUAGES) <= git_handler.code_extensions
    parser = CodeParser()
    for ext, code in CASES.items():
        filename = 'code.' + ext
        (tmp_path / filename).write_text(code)
        data = parser.parse_code(code, filename)
        assert data['functions']
        chunks = CodeChunker(10).chunk_code(code, data)
        assert any('run' in c['name'] for c in chunks)
    assert len(git_handler.get_code_files(tmp_path)) == len(CASES)


def test_partial_parse_is_warned_and_never_marked_complete():
    idx = SourceIndex({'code.js': {'code': 'function good(x){return x;} function broken( {'}})
    assert idx.diagnostics
    assert any(s['name'] == 'good' for s in idx.symbols.values())
    good = next(s for s in idx.symbols.values() if s['name'] == 'good')
    chunk, warnings = idx.workflow(good)
    assert not chunk['context_complete']
    assert any('Partial' in w for w in warnings)


def test_unresolved_names_are_retained_in_tiered_csv_metadata():
    idx = SourceIndex({'code.js': {'code': 'function run(receiver){return receiver.work();}'}})
    root = next(iter(idx.symbols.values()))
    chunk, _ = idx.workflow(root)
    assert 'receiver.work' in chunk['call_tiers'][1][0]
    assert 'unresolved' in chunk['call_tiers'][1][0]
