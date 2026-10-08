"""Syntax adapters for every language advertised by CodeParser.

Resolution is intentionally static and conservative. Unknown receivers and
callbacks retain their source expressions without inventing implementation files.
The pinned language pack bundles grammars; no runtime grammar download is used.
"""
import posixpath
import re
from functools import lru_cache
from pathlib import PurePosixPath


EXTENSION_LANGUAGES = {
    '.py': 'python', '.c': 'cpp', '.h': 'cpp', '.cpp': 'cpp', '.cc': 'cpp',
    '.cxx': 'cpp', '.hpp': 'cpp', '.hh': 'cpp', '.hxx': 'cpp', '.h++': 'cpp',
    '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'tsx',
    '.java': 'java', '.cs': 'csharp', '.go': 'go', '.rs': 'rust', '.rb': 'ruby',
    '.php': 'php', '.swift': 'swift', '.kt': 'kotlin', '.kts': 'kotlin',
    '.scala': 'scala', '.r': 'r', '.m': 'matlab',
}
GRAMMARS = {'csharp': 'csharp', 'tsx': 'tsx'}
FUNCTION_NODES = {
    'javascript': {'function_declaration', 'function_expression', 'arrow_function', 'method_definition', 'generator_function_declaration'},
    'typescript': {'function_declaration', 'function_expression', 'arrow_function', 'method_definition', 'generator_function_declaration'},
    'tsx': {'function_declaration', 'function_expression', 'arrow_function', 'method_definition', 'generator_function_declaration'},
    'java': {'method_declaration', 'constructor_declaration'},
    'csharp': {'method_declaration', 'constructor_declaration', 'local_function_statement'},
    'go': {'function_declaration', 'method_declaration'},
    'rust': {'function_item'}, 'ruby': {'method', 'singleton_method'},
    'php': {'function_definition', 'method_declaration'},
    'swift': {'function_declaration', 'init_declaration'},
    'kotlin': {'function_declaration', 'secondary_constructor'},
    'scala': {'function_definition'}, 'r': {'function_definition'},
    'matlab': {'function_definition'},
}
CALL_NODES = {
    'java': {'method_invocation', 'object_creation_expression'},
    'csharp': {'invocation_expression', 'object_creation_expression'},
    'ruby': {'call'}, 'php': {'function_call_expression', 'member_call_expression', 'scoped_call_expression', 'object_creation_expression'},
    'r': {'call'}, 'matlab': {'function_call'},
}
SCOPE_NODES = {
    'class_declaration', 'class_definition', 'class', 'module', 'object_definition',
    'trait_definition', 'trait_item', 'struct_declaration', 'interface_declaration', 'enum_declaration',
    'object_declaration', 'record_declaration', 'impl_item', 'mod_item',
    'namespace_declaration', 'namespace_definition',
}
JS_LANGUAGES = {'javascript', 'typescript', 'tsx'}


def walk(node):
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(current.named_children))


def text(node):
    return node.text.decode('utf-8') if node is not None else ''


def field(node, *names):
    for name in names:
        result = node.child_by_field_name(name)
        if result is not None:
            return result
    return None


def first(node, *types):
    return next((child for child in node.named_children if child.type in types), None)


def module_name(filename):
    return str(PurePosixPath(filename).with_suffix('')).replace('/', '.')


@lru_cache(maxsize=None)
def parser_for(language):
    from tree_sitter_language_pack import get_parser
    return get_parser(GRAMMARS.get(language, language))


def js_module(filename, requested, files):
    if not requested.startswith('.'):
        return None
    base = posixpath.normpath(str(PurePosixPath(filename).parent / requested))
    if base in files:
        return base
    stem = str(PurePosixPath(base).with_suffix('')) if PurePosixPath(base).suffix else base
    choices = [stem + ext for ext in ('.js', '.jsx', '.ts', '.tsx')]
    choices += [base + '/index' + ext for ext in ('.js', '.jsx', '.ts', '.tsx')]
    found = [p for p in choices if p in files]
    return found[0] if len(found) == 1 else None


def rust_module(filename):
    parts = list(PurePosixPath(filename).with_suffix('').parts)
    if 'src' in parts:
        parts = parts[parts.index('src') + 1:]
    if parts[-1] in {'lib', 'main', 'mod'}:
        parts.pop()
    return '.'.join(['crate'] + parts)


def syntax_symbols(code, filename, language, files, diagnostics):
    root = parser_for(language).parse(code.encode('utf-8')).root_node
    if root.has_error:
        diagnostics.append(f'Partial {language} syntax parse: {filename}; erroneous definitions are skipped')
    functions = FUNCTION_NODES[language]
    call_nodes = CALL_NODES.get(language, {'call_expression'})
    imports, wildcard_imports, related_files = {}, [], set()
    package = ''
    export_aliases = {}
    commonjs_exports = {}

    # Namespace/package metadata comes from declaration nodes, not repository-wide name guesses.
    for node in root.named_children:
        if node.type in {'package_declaration', 'package_header', 'package_clause'}:
            package += ('.' if package else '') + re.sub(r'^package\s+|[;\s]+$', '', text(node)).strip()
        elif node.type == 'file_scoped_namespace_declaration':
            package = text(field(node, 'name'))
        elif language == 'php' and node.type == 'namespace_definition' and field(node, 'body') is None:
            package = text(field(node, 'name')).replace('\\', '.')
    if language in JS_LANGUAGES:
        namespace = module_name(filename)
    elif language == 'rust':
        namespace = rust_module(filename)
    elif language == 'go':
        directory = str(PurePosixPath(filename).parent).replace('/', '.')
        namespace = (directory + '.' if directory != '.' else '') + package
    elif language in {'swift', 'r', 'matlab'}:
        namespace = str(PurePosixPath(filename).parent).replace('/', '.')
        namespace = namespace if namespace != '.' else '<root>'
    else:
        namespace = package

    for node in walk(root):
        raw = text(node)
        if language in JS_LANGUAGES and node.type == 'assignment_expression':
            left, right = text(field(node, 'left')), field(node, 'right')
            if left.startswith(('exports.', 'module.exports.')):
                commonjs_exports.setdefault(text(right), []).append(left.split('.')[-1])
            elif left == 'module.exports' and right:
                if right.type == 'identifier':
                    commonjs_exports.setdefault(text(right), []).append('default')
                elif right.type == 'object':
                    for member in right.named_children:
                        if member.type == 'shorthand_property_identifier':
                            commonjs_exports.setdefault(text(member), []).append(text(member))
                        elif member.type == 'pair':
                            commonjs_exports.setdefault(text(field(member, 'value')), []).append(text(field(member, 'key')))
        if language in JS_LANGUAGES and node.type == 'import_statement':
            path = text(field(node, 'source')).strip('\'"')
            target = js_module(filename, path, files)
            if target:
                related_files.add(target)
            else:
                diagnostics.append(f'Import external/unresolved: {path} from {filename}')
            clause = first(node, 'import_clause')
            if clause:
                for spec in walk(clause):
                    if spec.type == 'import_specifier':
                        name = text(field(spec, 'name'))
                        imports[text(field(spec, 'alias')) or name] = {'file': target, 'export': name}
                    elif spec.type == 'namespace_import':
                        imports[text(first(spec, 'identifier'))] = {'file': target, 'export': '*'}
                for spec in clause.named_children:
                    if spec.type == 'identifier':
                        imports[text(spec)] = {'file': target, 'export': 'default'}
        elif language in JS_LANGUAGES and node.type == 'export_specifier':
            export_aliases.setdefault(text(field(node, 'name')), []).append(text(field(node, 'alias')) or text(field(node, 'name')))
        elif language in JS_LANGUAGES and node.type == 'variable_declarator':
            value = field(node, 'value')
            if value and value.type == 'call_expression' and text(field(value, 'function')) == 'require':
                arguments = field(value, 'arguments')
                literal = first(arguments, 'string') if arguments else None
                target = js_module(filename, text(literal).strip('\'"'), files) if literal else None
                if target:
                    related_files.add(target)
                binding = field(node, 'name')
                if binding and binding.type == 'identifier':
                    imports[text(binding)] = {'file': target, 'export': '*'}
                elif binding and binding.type == 'object_pattern':
                    for spec in binding.named_children:
                        if spec.type == 'pair_pattern':
                            imports[text(field(spec, 'value'))] = {'file': target, 'export': text(field(spec, 'key'))}
                        elif spec.type == 'shorthand_property_identifier_pattern':
                            imports[text(spec)] = {'file': target, 'export': text(spec)}
        elif language in {'java', 'kotlin', 'scala'} and node.type in {'import_declaration', 'import_header'}:
            declaration = re.sub(r'^import\s+(?:static\s+)?|[;\s]+$', '', raw).strip()
            match = re.fullmatch(r'([\w.]+)(?:\s+as\s+(\w+))?', declaration)
            if match:
                imports[match[2] or match[1].split('.')[-1]] = match[1]
            elif declaration.endswith('.*'):
                wildcard_imports.append(declaration[:-2])
        elif language == 'csharp' and node.type == 'using_directive':
            declaration = re.sub(r'^using\s+|[;\s]+$', '', raw).strip()
            if declaration.startswith('static '):
                wildcard_imports.append(declaration[7:].strip())
            elif '=' in declaration:
                alias, target = declaration.split('=', 1)
                imports[alias.strip()] = target.strip()
            else:
                wildcard_imports.append(declaration)
        elif language == 'go' and node.type == 'import_spec':
            path = text(field(node, 'path')).strip('\'"`')
            alias = text(field(node, 'name')) or path.split('/')[-1]
            imports[alias] = {'go_path': path}
        elif language == 'rust' and node.type == 'use_declaration':
            match = re.fullmatch(r'use\s+([\w:]+)(?:\s+as\s+(\w+))?;', raw)
            if match:
                imports[match[2] or match[1].split('::')[-1]] = match[1].replace('::', '.')
        elif language == 'php' and node.type == 'namespace_use_declaration':
            match = re.fullmatch(r'use\s+(?:function\s+)?([\w\\]+)(?:\s+as\s+(\w+))?;', raw)
            if match:
                target = match[1].replace('\\', '.')
                imports[match[2] or target.split('.')[-1]] = target

    def name_of(node):
        if language == 'r':
            parent = node.parent
            if parent and parent.type == 'binary_operator' and field(parent, 'rhs') == node:
                return text(field(parent, 'lhs'))
            return ''
        if language in JS_LANGUAGES and node.type in {'arrow_function', 'function_expression'}:
            parent = node.parent
            if parent and parent.type in {'variable_declarator', 'pair', 'assignment_expression', 'public_field_definition', 'field_definition'}:
                return text(field(parent, 'name', 'key', 'left', 'property'))
            if parent and parent.type == 'export_statement':
                return 'default'
        name = field(node, 'name')
        if name and name.type in {'function', 'user_type'}:
            name = first(node, 'simple_identifier', 'identifier')
        if language == 'kotlin':
            name = first(node, 'simple_identifier')
        if not name and language in JS_LANGUAGES and node.parent and node.parent.type == 'export_statement':
            return 'default'
        return text(name)

    def scopes_of(node):
        result = []
        parent = node.parent
        while parent:
            if parent.type in SCOPE_NODES:
                name = text(field(parent, 'name', 'type'))
                if not name and language == 'kotlin':
                    name = text(first(parent, 'type_identifier'))
                if name:
                    result.insert(0, name.replace('::', '.').replace('\\', '.'))
            elif parent.type in functions:
                name = name_of(parent)
                if name:
                    result.insert(0, name)
            elif language in JS_LANGUAGES and parent.type == 'object' and parent.parent and parent.parent.type == 'variable_declarator':
                result.insert(0, text(field(parent.parent, 'name')))
            parent = parent.parent
        if language == 'go':
            receiver = field(node, 'receiver')
            if receiver:
                declaration = first(receiver, 'parameter_declaration')
                receiver_type = text(field(declaration, 'type')).lstrip('*') if declaration else ''
                if receiver_type:
                    result.append(receiver_type)
        return result

    def body_of(node):
        return field(node, 'body') or first(node, 'function_body', 'block')

    records = []
    for node in walk(root):
        if node.type not in functions:
            continue
        name, body = name_of(node), body_of(node)
        if not name or body is None:
            continue  # Abstract/interface signatures are context, not implementations.
        if node.has_error:
            diagnostics.append(f'Invalid/incomplete {language} definition: {filename}:{node.start_point.row + 1}')
            continue
        scopes = scopes_of(node)
        record_namespace = namespace
        if language == 'matlab' and not scopes and records:
            record_namespace = namespace + '.' + PurePosixPath(filename).stem
        qualified = '.'.join(p for p in [record_namespace] + scopes + [name] if p)
        owner = node.parent if language == 'r' or (language in JS_LANGUAGES and node.type in {'arrow_function', 'function_expression'}) else node
        params = field(node, 'parameters') or first(node, 'function_value_parameters', 'function_arguments')
        param_nodes = list(params.named_children) if params else [c for c in node.named_children if c.type == 'parameter']
        parameter_names = set()
        for parameter in param_nodes:
            ident = field(parameter, 'name', 'pattern') or first(parameter, 'simple_identifier', 'identifier')
            parameter_names.add(text(ident) or text(parameter))
        receiver = field(node, 'receiver')
        self_names = {'this', 'self', '$this', 'cls', 'Self'}
        if receiver:
            declaration = first(receiver, 'parameter_declaration')
            if declaration:
                self_names.add(text(field(declaration, 'name')))
        if language == 'matlab' and scopes and param_nodes:
            self_names.add(text(param_nodes[0]))
        calls = []
        pending = [body]
        while pending:
            call = pending.pop()
            if call != body and (call.type in functions or call.type in {'lambda_expression', 'closure_expression', 'func_literal'}):
                continue
            pending.extend(reversed(call.named_children))
            if call.type not in call_nodes:
                if language == 'rust' and call.type == 'macro_invocation':
                    calls.append({'name': None, 'expression': text(call), 'arity': None,
                                  'line': call.start_point.row + 1, 'lookup_names': []})
                continue
            callee = field(call, 'function', 'method', 'name')
            obj = field(call, 'object', 'scope')
            if language in {'swift', 'kotlin'}:
                callee = next((c for c in call.named_children if c.type != 'call_suffix'), None)
            elif language == 'matlab' and call.parent and call.parent.type == 'field_expression':
                obj = field(call.parent, 'object')
            if callee and callee.type in {'member_expression', 'member_access_expression', 'selector_expression', 'field_expression', 'navigation_expression'}:
                raw = text(callee)
            else:
                raw = (text(obj) + '.' if obj else '') + text(callee)
            raw = raw.replace('->', '.').replace('::', '.').replace('\\', '.')
            if call.type == 'object_creation_expression':
                raw = text(field(call, 'type')) + '.<constructor>'
            lookup_names, imported = [], None
            parts = raw.split('.')
            if parts[0] in self_names:
                lookup_names = ['.'.join([record_namespace] + scopes + parts[1:]).strip('.')]
            elif parts[0] in parameter_names:
                pass  # Receiver/callback type dispatch is not inferred from its spelling.
            elif parts[0] in imports:
                binding = imports[parts[0]]
                if isinstance(binding, dict):
                    imported = {**binding, 'members': parts[1:]}
                else:
                    lookup_names = ['.'.join([binding] + parts[1:])]
            elif language == 'rust' and parts[0] in {'crate', 'super'}:
                base = namespace.split('.')
                while parts and parts[0] == 'super':
                    base = base[:-1]
                    parts = parts[1:]
                lookup_names = ['.'.join(parts if parts and parts[0] == 'crate' else base + parts)]
            elif len(parts) == 1:
                lookup_names = ['.'.join(p for p in [record_namespace] + scopes[:i] + [raw] if p)
                                for i in range(len(scopes), -1, -1)]
                lookup_names.insert(0, qualified + '.' + raw)
                lookup_names += [prefix + '.' + raw for prefix in wildcard_imports]
                if record_namespace != namespace:
                    lookup_names.append(namespace + '.' + raw)
            elif re.fullmatch(r'[\w<>]+(?:\.[\w]+)+', raw):
                # A syntactically qualified class/object/module target, never a basename fallback.
                lookup_names = [prefix + '.' + raw for prefix in wildcard_imports]
                lookup_names += ['.'.join(p for p in [record_namespace] + scopes[:i] + [raw] if p)
                                 for i in range(len(scopes), -1, -1)] + [raw]
            arguments = field(call, 'arguments') or first(call, 'arguments')
            # Retain arity for overload checks where it is structurally unambiguous.
            arity = len(arguments.named_children) if arguments else None
            if language not in {'java', 'csharp', 'rust', 'go'}:
                arity = None  # Defaults, keywords, rest/curried args need richer semantic analysis.
            calls.append({'name': raw or None, 'expression': raw or text(call),
                          'arity': arity, 'line': call.start_point.row + 1,
                          'lookup_names': list(dict.fromkeys(lookup_names)), 'import_ref': imported})
        exports = list(export_aliases.get(name, []))
        if language in JS_LANGUAGES:
            parent = owner.parent
            export_node = parent if parent and parent.type == 'export_statement' else None
            if parent and parent.type in {'lexical_declaration', 'variable_declaration'}:
                export_node = parent.parent if parent.parent and parent.parent.type == 'export_statement' else None
            if export_node:
                exports.append('default' if re.match(r'export\s+default\b', text(export_node)) else name)
            exports += commonjs_exports.get(name, [])
            if name.startswith(('module.exports.', 'exports.')):
                exports.append(name.split('.')[-1])
                name = name.split('.')[-1]
                qualified = '.'.join(p for p in [record_namespace] + scopes + [name] if p)
            ancestor = node.parent
            while ancestor:
                if ancestor.type == 'class_declaration' and ancestor.parent and ancestor.parent.type == 'export_statement':
                    class_name = text(field(ancestor, 'name'))
                    if class_name:
                        prefix = 'default' if re.match(r'export\s+default\b', text(ancestor.parent)) else class_name
                        exports.append(prefix + '.' + name)
                ancestor = ancestor.parent
        is_static = language == 'java' and bool(re.search(r'\b(static|private|final)\b', text(first(node, 'modifiers'))))
        dynamic = (language == 'java' and bool(scopes) and not is_static and node.type == 'method_declaration')
        dynamic = dynamic or (language == 'csharp' and bool(re.search(r'\b(virtual|override|abstract)\b', text(node).split('{', 1)[0])))
        arity = len(param_nodes)
        if language == 'go':
            arity = sum(max(1, sum(p.field_name_for_child(i) == 'name' for i in range(len(p.children)))) for p in param_nodes)
        records.append({
            'name': name, 'qualified_name': qualified, 'language': language,
            'file': filename, 'line': owner.start_point.row + 1, 'column': owner.start_point.column,
            'end_line': owner.end_point.row + 1, 'code': text(owner), 'is_definition': True,
            'arity': arity, 'min_arity': arity, 'internal': False,
            'variadic': any('...' in text(p) for p in param_nodes), 'dynamic': dynamic,
            'calls': calls, 'related_files': sorted(related_files), 'exports': list(set(exports)),
            'namespace': namespace,
            'context_warnings': [f'Partial syntax parse in {filename}'] if root.has_error else [],
        })
    if not records and not root.has_error:
        diagnostics.append(f'No named implementation definitions found in {filename} ({language}); declaration/data-only file or unsupported callable syntax')
    return records
