"""Source-backed symbols and conservative call resolution across supported languages.

This is a syntax index, not a compiler: ambiguous overloads, virtual dispatch,
macros and dynamic calls stay unresolved instead of being matched by basename.
"""
import ast
import posixpath
import re
from collections import defaultdict, deque
from pathlib import PurePosixPath
from language_adapters import EXTENSION_LANGUAGES, syntax_symbols


CPP_EXTENSIONS = {'.c', '.h', '.cpp', '.cc', '.cxx', '.hpp', '.hh', '.hxx', '.h++'}


def descendants(node):
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(current.named_children))


def cpp_symbols(code, filename):
    from tree_sitter import Language, Parser
    import tree_sitter_cpp

    tree = Parser(Language(tree_sitter_cpp.language())).parse(code.encode('utf-8'))
    if tree.root_node.has_error:
        raise ValueError(f'C/C++ syntax could not be indexed reliably: {filename}')

    def text(node):
        return node.text.decode('utf-8') if node else ''

    def scope(node):
        parts = []
        parent = node.parent
        while parent:
            if parent.type in {'namespace_definition', 'class_specifier', 'struct_specifier'}:
                name = text(parent.child_by_field_name('name'))
                parts.insert(0, name or f'<anonymous@{filename}>')
            parent = parent.parent
        return parts

    records = []
    for node in descendants(tree.root_node):
        if node.type != 'function_declarator':
            continue
        owner = node.parent
        while owner and owner.type not in {'function_definition', 'declaration', 'field_declaration'}:
            owner = owner.parent
        if not owner:
            continue
        # Exclude function-pointer variables and local declarations.
        if any(p.type == 'function_definition' for p in _parents(owner)):
            continue
        name_node = node.child_by_field_name('declarator')
        if not name_node or name_node.type not in {
            'identifier', 'field_identifier', 'qualified_identifier', 'destructor_name', 'operator_name'
        }:
            continue
        name = text(name_node)
        qualified = '::'.join(scope(owner) + [name]) if not name.startswith('::') else name[2:]
        parameters = node.child_by_field_name('parameters')
        params = [p for p in parameters.named_children if p.type in {
            'parameter_declaration', 'optional_parameter_declaration'
        }] if parameters else []
        parameter_types = tuple(re.sub(r'\s+', '', text(p.child_by_field_name('type')) +
                                ''.join(text(c) for c in p.children if c.type == 'type_qualifier') +
                                ('*' if '*' in text(p.child_by_field_name('declarator')) else '') +
                                ('&' if '&' in text(p.child_by_field_name('declarator')) else '')) for p in params)
        body = owner.child_by_field_name('body') if owner.type == 'function_definition' else None
        receiver_types = {}
        for declaration in descendants(owner):
            if declaration.type in {'parameter_declaration', 'optional_parameter_declaration', 'declaration'}:
                type_name = text(declaration.child_by_field_name('type'))
                decl = declaration.child_by_field_name('declarator')
                while decl and decl.type in {'pointer_declarator', 'reference_declarator', 'init_declarator'}:
                    decl = decl.child_by_field_name('declarator') or next(iter(decl.named_children), None)
                if decl and decl.type == 'identifier':
                    receiver_types[text(decl)] = type_name
        calls = []
        if body:
            for call in descendants(body):
                if call.type != 'call_expression':
                    continue
                callee = call.child_by_field_name('function')
                call_name = text(callee)
                if callee.type == 'identifier' and call_name in receiver_types:
                    call_name = None  # A local callable shadows a repository function.
                member = callee.type == 'field_expression'
                if member:
                    receiver = text(callee.child_by_field_name('argument'))
                    method = text(callee.child_by_field_name('field'))
                    if receiver == 'this':
                        call_name = qualified.rsplit('::', 1)[0] + '::' + method
                    elif receiver in receiver_types:
                        call_name = receiver_types[receiver] + '::' + method
                    else:
                        call_name = None
                args = call.child_by_field_name('arguments')
                calls.append({'name': call_name, 'expression': text(callee),
                              'arity': len(args.named_children) if args else 0,
                              'line': call.start_point.row + 1})
        records.append({
            'name': name.split('::')[-1], 'qualified_name': qualified,
            'file': filename, 'line': owner.start_point.row + 1,
            'column': owner.start_point.column,
            'end_line': owner.end_point.row + 1,
            'code': text(owner), 'is_definition': body is not None,
            'arity': len(params),
            'parameter_types': parameter_types,
            'dynamic': any(c.type in {'virtual', 'virtual_specifier'}
                           or text(c) in {'virtual', 'override', 'final'} for c in owner.children + node.children),
            'min_arity': sum(p.type != 'optional_parameter_declaration' for p in params),
            'variadic': bool(parameters and any(p.type == 'variadic_parameter' for p in parameters.named_children)),
            'internal': 'static' in [text(c) for c in owner.children if c.type == 'storage_class_specifier']
                        and not any(p.type in {'class_specifier', 'struct_specifier'} for p in _parents(owner)),
            'calls': calls, 'language': 'cpp',
        })
    return records


def _parents(node):
    node = node.parent
    while node:
        yield node
        node = node.parent


def python_symbols(code, filename):
    tree = ast.parse(code)
    module = str(PurePosixPath(filename).with_suffix('')).replace('/', '.')
    if module.endswith('.__init__'):
        module = module[:-9]
    imports = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                package = module.split('.') if filename.endswith('/__init__.py') else module.split('.')[:-1]
                base = '.'.join(package[:len(package) - node.level + 1] + ([base] if base else []))
            for alias in node.names:
                imports[alias.asname or alias.name] = base + '.' + alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
    records = []

    def visit(node, scopes):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = '.'.join([module] + scopes + [node.name])
            calls = []
            def calls_in(current):
                if current is not node and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    return
                if isinstance(current, ast.Call):
                    raw = ast.unparse(current.func)
                    parts = raw.split('.')
                    if parts[0] in {'self', 'cls'} and scopes:
                        name = '.'.join([module] + scopes + parts[1:])
                    elif parts[0] in imports:
                        name = '.'.join([imports[parts[0]]] + parts[1:])
                    elif isinstance(current.func, ast.Name):
                        name = '.'.join([module] + scopes + [raw])
                    else:
                        name = None
                    calls.append({'name': name, 'expression': raw, 'arity': None, 'line': current.lineno})
                for child in ast.iter_child_nodes(current):
                    calls_in(child)
            calls_in(node)
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            records.append({'name': node.name, 'qualified_name': qualified,
                            'file': filename, 'line': start, 'end_line': node.end_lineno,
                            'code': '\n'.join(code.splitlines()[start-1:node.end_lineno]),
                            'is_definition': True, 'calls': calls, 'arity': None,
                            'internal': False, 'language': 'python'})
        next_scopes = scopes + [node.name] if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else scopes
        for child in ast.iter_child_nodes(node):
            visit(child, next_scopes)
    visit(tree, [])
    return records


class SourceIndex:
    def __init__(self, parsed_data):
        self.files = parsed_data
        self.symbols = {}
        self.by_name = defaultdict(list)
        self.declarations = defaultdict(list)
        self.exports = defaultdict(list)
        self.diagnostics = []
        for filename, data in sorted(parsed_data.items()):
            try:
                ext = PurePosixPath(filename).suffix.lower()
                if ext in CPP_EXTENSIONS:
                    records = cpp_symbols(data['code'], filename)
                elif ext == '.py':
                    records = python_symbols(data['code'], filename)
                elif ext in EXTENSION_LANGUAGES:
                    records = syntax_symbols(data['code'], filename, EXTENSION_LANGUAGES[ext],
                                             parsed_data, self.diagnostics)
                else:
                    self.diagnostics.append(f'Functional indexing unsupported for {filename}; skipped')
                    continue
                for record in records:
                    record['symbol_id'] = f"{filename}:{record['line']}:{record.get('column', 0)}:{record['qualified_name']}"
                    if record['is_definition']:
                        self.symbols[record['symbol_id']] = record
                        self.by_name[record['qualified_name']].append(record)
                        for exported in record.get('exports', []):
                            self.exports[(filename, exported)].append(record)
                    else:
                        self.declarations[record['qualified_name']].append(record)
            except (ImportError, ValueError, SyntaxError) as exc:
                self.diagnostics.append(str(exc))
        self.edges = {sid: self._resolve_calls(symbol) for sid, symbol in self.symbols.items()}

    def _resolve_adapter_calls(self, caller):
        edges = []
        for call in caller['calls']:
            candidates = []
            imported = call.get('import_ref')
            if imported:
                if imported.get('file'):
                    exported = imported['export']
                    members = imported.get('members', [])
                    if exported == '*':
                        exported = '.'.join(members)
                    elif members:
                        exported += '.' + '.'.join(members)
                    candidates = self.exports.get((imported['file'], exported), [])
                elif imported.get('go_path'):
                    path = imported['go_path']
                    directories = {str(PurePosixPath(s['file']).parent) for s in self.symbols.values()
                                   if s['language'] == 'go'
                                   and (path == str(PurePosixPath(s['file']).parent)
                                        or path.endswith('/' + str(PurePosixPath(s['file']).parent)))}
                    if len(directories) == 1:
                        members = '.'.join(imported.get('members', []))
                        candidates = [s for s in self.symbols.values() if s['language'] == 'go'
                                      and str(PurePosixPath(s['file']).parent) in directories
                                      and s['qualified_name'] == s['namespace'] + '.' + members]
            else:
                for name in call.get('lookup_names', []):
                    candidates = [s for s in self.by_name.get(name, []) if s['language'] == caller['language']]
                    if candidates:
                        break
            if call['arity'] is not None:
                candidates = [s for s in candidates if s['min_arity'] <= call['arity']
                              and (s.get('variadic') or call['arity'] <= s['arity'])]
            resolved = candidates[0]['symbol_id'] if len(candidates) == 1 else None
            dynamic = bool(resolved and candidates[0].get('dynamic'))
            if dynamic:
                resolved = None
            edges.append({**call, 'caller': caller['symbol_id'], 'callee': resolved,
                          'candidate_definitions': [{'name': s['qualified_name'], 'file': s['file'],
                                                     'line': s['line']} for s in candidates],
                          'resolution': 'dynamic' if dynamic else ('resolved' if resolved else ('ambiguous' if candidates else 'unresolved'))})
        return edges

    def _resolve_calls(self, caller):
        if caller['language'] not in {'cpp', 'python'}:
            return self._resolve_adapter_calls(caller)
        edges = []
        separator = '::' if caller['language'] == 'cpp' else '.'
        scope = caller['qualified_name'].split(separator)[:-1]
        for call in caller['calls']:
            candidates = []
            name = call['name']
            if name:
                if caller['language'] == 'cpp' and not name.startswith('::'):
                    # Lookup from innermost scope to global scope; never search all basenames.
                    names = [separator.join(scope[:i] + [name]) for i in range(len(scope), -1, -1)]
                else:
                    names = [name.lstrip(':')]
                    if caller['language'] == 'python':
                        if name == '.'.join(scope + [call['expression']]):
                            names.insert(0, caller['qualified_name'] + '.' + call['expression'])
                        # A method may call a module-level helper by its bare name.
                        names += ['.'.join(scope[:i] + [call['expression']]) for i in range(len(scope)-1, 0, -1)]
                for lookup in names:
                    available = [s for s in self.by_name.get(lookup, [])
                                 if s['language'] == caller['language']
                                 and (not s['internal'] or s['file'] == caller['file'])]
                    local_static = [s for s in available if s['internal'] and s['file'] == caller['file']]
                    if local_static:
                        available = local_static
                    if available:
                        candidates = available
                        break
                if call['arity'] is not None:
                    def min_arity(symbol):
                        declarations = [d for d in self.declarations.get(symbol['qualified_name'], [])
                                        if d.get('parameter_types') == symbol.get('parameter_types')]
                        return min([symbol['min_arity']] + [d['min_arity'] for d in declarations])
                    candidates = [s for s in candidates if min_arity(s) <= call['arity']
                                  and (s.get('variadic') or call['arity'] <= s['arity'])]
            resolved = candidates[0]['symbol_id'] if len(candidates) == 1 else None
            dynamic = bool(resolved and (candidates[0].get('dynamic') or any(
                d.get('dynamic') for d in self.declarations.get(candidates[0]['qualified_name'], [])
            )))
            if dynamic:
                resolved = None
            edges.append({**call, 'caller': caller['symbol_id'], 'callee': resolved,
                          'resolution': 'dynamic' if dynamic else ('resolved' if resolved else ('ambiguous' if candidates else 'unresolved'))})
        return edges

    def workflow(self, root, max_chars=60000, max_depth=8):
        """Keep each definition intact; record omitted dependencies explicitly."""
        queue = deque([(root['symbol_id'], 0)])
        visited, tiers, evidence, blocks, edges, warnings = set(), defaultdict(list), {}, [], [], []
        used = 0
        while queue:
            sid, tier = queue.popleft()
            if sid in visited:
                continue
            visited.add(sid)
            symbol = self.symbols[sid]
            warnings.extend(symbol.get('context_warnings', []))
            if tier:
                tiers[tier].append(f"{symbol['qualified_name']} [{symbol['file']}:{symbol['line']}]")
            block = f"SYMBOL {sid}\n" + '\n'.join(
                f"{i}: {line}" for i, line in enumerate(symbol['code'].splitlines(), symbol['line']))
            if used + len(block) > max_chars:
                warnings.append(f'Context budget exceeded: {sid}')
                if tier == 0:
                    return None, warnings
            else:
                evidence[sid] = {'file': symbol['file'], 'start_line': symbol['line'], 'end_line': symbol['end_line']}
                blocks.append(block)
                used += len(block)
            for edge in self.edges[sid]:
                edges.append(edge)
                if not edge['callee']:
                    warnings.append(f"{edge['resolution']}: {edge['expression']} at {symbol['file']}:{edge['line']}")
                    if tier < max_depth:
                        tiers[tier + 1].append(
                            f"{edge['expression']} [{edge['resolution']} at {symbol['file']}:{edge['line']}]"
                        )
                elif tier < max_depth:
                    queue.append((edge['callee'], tier + 1))
                elif edge['callee'] not in visited:
                    warnings.append(f"Call depth exceeded: {edge['callee']}")
        # Include file context (includes, constants, types and declarations) if it fits.
        related = {self.symbols[sid]['file'] for sid in visited}
        related.update(f for sid in visited for f in self.symbols[sid].get('related_files', []))
        related.update(d['file'] for sid in visited
                       for d in self.declarations.get(self.symbols[sid]['qualified_name'], []))
        include_queue = deque(sorted(related))
        while include_queue:
            filename = include_queue.popleft()
            if PurePosixPath(filename).suffix.lower() not in CPP_EXTENSIONS:
                continue
            for delimiter, included in re.findall(r'^\s*#\s*include\s*(["<])([^">]+)[">]', self.files[filename]['code'], re.MULTILINE):
                local = posixpath.normpath(str(PurePosixPath(filename).parent / included))
                # Includes can use an include-directory path, but duplicate suffixes are ambiguous.
                candidates = ([local] if local in self.files else
                              [f for f in self.files if f == included or f.endswith('/' + included)])
                if len(candidates) != 1:
                    if candidates or delimiter == '"':
                        warnings.append(f'Include unresolved/ambiguous: {included} from {filename}')
                    continue
                if candidates[0] not in related:
                    related.add(candidates[0])
                    include_queue.append(candidates[0])
        for filename in sorted(related):
            source = self.files[filename]['code']
            file_id = f'file:{filename}'
            block = f"FILE CONTEXT SYMBOL {file_id}\n" + '\n'.join(
                f'{i}: {line}' for i, line in enumerate(source.splitlines(), 1))
            if used + len(block) <= max_chars:
                blocks.append(block)
                evidence[file_id] = {'file': filename, 'start_line': 1,
                                     'end_line': len(source.splitlines())}
                used += len(block)
            else:
                warnings.append(f'File context omitted: {filename}')
        return {'name': root['qualified_name'], 'type': 'function', 'code': '\n\n'.join(blocks),
                'line_start': root['line'], 'line_end': root['end_line'],
                'file': root['file'], 'symbol_id': root['symbol_id'],
                'evidence_sources': evidence, 'direct_calls': self.edges[root['symbol_id']],
                'call_edges': edges, 'call_tiers': dict(tiers),
                'related_files': sorted(related), 'context_warnings': sorted(set(warnings)),
                'context_complete': not warnings}, warnings
