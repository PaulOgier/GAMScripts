#!/usr/bin/env python3
"""
GAM Script Checker: verb table builder
=============================================================================
Copyright (c) 2026 Paul Ogier, Outsource House (South Africa)
Website: https://osh.co.za | Email: support@osh.co.za
Training provided by Taming.Tech (https://taming.tech)

Google Workspace GAM7 Course on Udemy   https://taming.tech/GAMCourse
Google Workspace Admin Course on Udemy  https://www.taming.tech/GoogleWorkspaceAdmin
Google Workspace End-User Course on Udemy  https://www.taming.tech/TheCompleteWorkspaceCourse

Licence: Apache License 2.0 (full text in LICENSE at the repository root).
The plain-English summary, trademark note and disclaimer in gamcheck.py
apply to this file too. Keep this attribution block intact if you
redistribute it (Apache 2.0 clause 4(c)).

Provided "AS IS", without warranty of any kind.
=============================================================================

Build the verb tables in verbs/ from a GAM source checkout.

The verb table comes from GAM's own command dispatcher (src/gam/__init__.py),
not from the wiki or memory, so what the checker recognises is exactly what
GAM parses. Re-run this whenever GAM7 is released; the version is stamped into
the output so a stale table is visible.

Usage:
    git clone --depth 1 https://github.com/GAM-team/GAM.git
    python3 build_verb_table.py GAM/src/gam > gam_verbs.json

It also reads the two older codebases people still run, so scripts written
for them can be recognised and flagged as version-specific:
    GAMADV-XTD3 (taers232c/GAMADV-XTD3): same table layout as GAM7.
    Legacy GAM 6.x (GAM-team/GAM tag v6.58): if/elif dispatch, walked separately.

The source is parsed with ast, never imported, so nothing in GAM runs.
"""
import ast
import json
import sys
from pathlib import Path

# Tables read out of __init__.py. Each is a dispatch map GAM consults while
# parsing a command line; see ProcessGAMCommand and the process*Commands helpers.
INIT_TABLES = [
    'BATCH_CSV_COMMANDS',
    'MAIN_COMMANDS', 'MAIN_COMMANDS_WITH_OBJECTS', 'MAIN_COMMANDS_OBJ_ALIASES',
    'COMMANDS_MAP', 'COMMANDS_ALIASES',
    'AUDIT_SUBCOMMANDS_WITH_OBJECTS',
    'OAUTH2_SUBCOMMANDS', 'OAUTH2_SUBCOMMAND_ALIASES',
    'CALENDAR_SUBCOMMANDS', 'CALENDAR_OLDACL_SUBCOMMANDS', 'CALENDAR_OLDACL_SUBCOMMAND_ALIASES',
    'CALENDARS_SUBCOMMANDS_WITH_OBJECTS', 'CALENDARS_SUBCOMMANDS_OBJECT_ALIASES',
    'COURSE_SUBCOMMANDS', 'COURSE_SUBCOMMAND_ALIASES',
    'RESOURCE_SUBCOMMANDS_WITH_OBJECTS', 'RESOURCE_SUBCOMMAND_ALIASES', 'RESOURCE_SUBCOMMANDS_OBJECT_ALIASES',
    'CROS_COMMANDS', 'CROS_COMMANDS_WITH_OBJECTS', 'CROS_COMMANDS_OBJ_ALIASES',
    'USER_COMMANDS', 'USER_COMMANDS_WITH_OBJECTS', 'USER_COMMANDS_ALIASES', 'USER_COMMANDS_OBJ_ALIASES',
    'CROS_COMMAND_CHOICE_MAP',
]

# Attributes of GamCLArgs (Cmd) that describe entities, selectors and the
# words that can precede the command proper.
CMD_ATTRS = [
    'USER_ENTITIES', 'CROS_ENTITIES', 'BROWSER_ENTITIES', 'ENTITY_ALIAS_MAP',
    'BASE_ENTITY_SELECTORS', 'USER_ENTITY_SELECTORS', 'CROS_ENTITY_SELECTORS',
    'USER_CSVDATA_ENTITY_SELECTORS', 'CROS_CSVDATA_ENTITY_SELECTORS',
    'BATCH_CMD', 'CSV_CMD', 'CSVTEST_CMD', 'LOOP_CMD', 'TBATCH_CMD', 'GAM_CMD',
    'SELECT_CMD', 'SHOWSECTIONS_CMD', 'SELECTFILTER_CMD', 'SELECTOUTPUTFILTER_CMD',
    'SELECTINPUTFILTER_CMD', 'CONFIG_CMD', 'MULTIPROCESSEXIT_CMD', 'REDIRECT_CMD',
    'USER_ENTITY_SELECTOR_ALL_SUBTYPES', 'CROS_ENTITY_SELECTOR_ALL_SUBTYPES',
]


class Unresolvable(Exception):
    """Raised when a table uses an expression this literal evaluator does not model."""


def evaluate(node, scope, cmd):
    """Turn a literal-ish AST node into plain data.

    Cmd.X resolves through the GamCLArgs class body, Act.X becomes the string
    'X', a name bound in scope becomes its value, and any other bare name is a
    handler function and becomes its name.
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List)):
        return [evaluate(e, scope, cmd) for e in node.elts]
    if isinstance(node, ast.Dict):
        return {evaluate(k, scope, cmd): evaluate(v, scope, cmd) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id == 'Cmd':
            if node.attr not in cmd:
                raise Unresolvable(f'Cmd.{node.attr}')
            return cmd[node.attr]
        if node.value.id == 'Act':
            return node.attr
    if isinstance(node, ast.Name):
        if node.id in scope:
            return scope[node.id]
        # Handlers are camelCase; an unresolved UPPER_CASE name is a table we
        # failed to load, and passing its name through as a string would
        # silently drop every verb in it.
        if node.id.isupper():
            raise Unresolvable(node.id)
        return node.id
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return evaluate(node.left, scope, cmd) + evaluate(node.right, scope, cmd)
    raise Unresolvable(ast.dump(node)[:120])


def class_constants(path, class_name):
    """Evaluate the simple assignments in a class body, in order."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name).body
    scope = {}
    for node in body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                scope[node.targets[0].id] = evaluate(node.value, scope, scope)
            except Unresolvable:
                pass
    return scope


def module_tables(path, names, cmd):
    """Evaluate the named top-level assignments of a module.

    Every top-level dict is evaluated as it is met, because the named tables
    reference helper dicts such as MAIN_ADD_CREATE_FUNCTIONS. A named table
    that cannot be evaluated is fatal.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    scope = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in names:
                scope[name] = evaluate(node.value, scope, cmd)
            elif isinstance(node.value, ast.Dict) and name.isupper():
                try:
                    scope[name] = evaluate(node.value, scope, cmd)
                except Unresolvable:
                    pass
    missing = [n for n in names if n not in scope]
    if missing:
        raise SystemExit(f'Tables not found in {path}: {missing}. GAM has changed shape; update INIT_TABLES.')
    return {n: scope[n] for n in names}


def config_variable_names(path):
    """Return the keys of GC.VAR_INFO, i.e. every name valid after 'gam config'."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                consts[target] = node.value.value
            elif target == 'VAR_INFO':
                return sorted(consts[k.id] for k in node.value.keys)
    raise SystemExit(f'VAR_INFO not found in {path}')


def gam_version(path):
    """Read __version__ from GAM's __init__.py without importing it."""
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == '__version__':
            return node.value.value
    raise SystemExit('__version__ not found')


def modern_pairs(t):
    """Flatten the dispatch tables into (scope, verb, object, action, handler) rows.

    object is None for verbs that take no object word. Aliases are not
    expanded here; the checker applies them the way getChoice does.
    """
    # batch, csv, csvtest, tbatch and loop wrap other gam commands; the checker
    # classifies what they wrap, but they still need to be recognised words.
    rows = [['main', verb, None, action, handler] for verb, (action, handler) in t['BATCH_CSV_COMMANDS'].items()]
    rows.append(['main', 'loop', None, 'PERFORM', 'doLoop'])

    def flat(scope, table):
        for verb, (action, handler) in table.items():
            rows.append([scope, verb, None, action, handler])

    def objs(scope, table):
        for verb, (action, objects) in table.items():
            for obj, handler in objects.items():
                rows.append([scope, verb, obj, action, handler])

    flat('main', t['MAIN_COMMANDS'])
    objs('main', t['MAIN_COMMANDS_WITH_OBJECTS'])
    flat('user', t['USER_COMMANDS'])
    objs('user', t['USER_COMMANDS_WITH_OBJECTS'])
    flat('cros', t['CROS_COMMANDS'])
    objs('cros', t['CROS_COMMANDS_WITH_OBJECTS'])
    flat('oauth', t['OAUTH2_SUBCOMMANDS'])
    flat('calendar', t['CALENDAR_SUBCOMMANDS'])
    flat('calendar', t['CALENDAR_OLDACL_SUBCOMMANDS'])
    objs('calendar', t['CALENDARS_SUBCOMMANDS_WITH_OBJECTS'])
    flat('course', t['COURSE_SUBCOMMANDS'])
    objs('resource', t['RESOURCE_SUBCOMMANDS_WITH_OBJECTS'])
    for verb, objects in t['AUDIT_SUBCOMMANDS_WITH_OBJECTS'].items():
        for obj, (action, handler) in objects.items():
            rows.append(['audit', verb, obj, action, handler])
    return rows


def _chain(node):
    """Yield (variable, values, body) for each branch of an if/elif chain.

    Only branches testing a bare name against string constants count; a
    branch with any other test ends the walk down that branch.
    """
    while isinstance(node, ast.If):
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and len(test.ops) == 1
                and isinstance(test.ops[0], (ast.Eq, ast.In))):
            right = test.comparators[0]
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                values = [right.value]
            elif isinstance(right, (ast.List, ast.Tuple)) and all(
                    isinstance(e, ast.Constant) and isinstance(e.value, str) for e in right.elts):
                values = [e.value for e in right.elts]
            else:
                values = None
            if values is not None:
                yield test.left.id, values, node.body
        node = node.orelse[0] if len(node.orelse) == 1 else None


def _first_call(body):
    """Name the first function called in a branch body, as its handler."""
    for stmt in body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Call):
                name = ast.unparse(sub.func)
                if name not in ('sys.exit', 'print') and not name.startswith('controlflow.'):
                    return name
    return None


def _walk_legacy(body, verbs, obj, scope, rows):
    """Descend nested if-chains; the variable 'command' holds verbs, any other holds objects."""
    # The first if-statement that is a name/constant chain; earlier ifs such
    # as the sys.version_info check are not dispatch.
    branches = next((b for b in (list(_chain(s)) for s in body if isinstance(s, ast.If)) if b), [])
    if not branches:
        if verbs:
            for verb in verbs:
                rows.append([scope, verb, obj, None, _first_call(body)])
        return
    for var, values, sub in branches:
        if var == 'command':
            narrowed = values if verbs is None else [v for v in values if v in verbs]
            _walk_legacy(sub, narrowed, obj, scope, rows)
        else:
            for value in values:
                _walk_legacy(sub, verbs, value, scope, rows)


def legacy_pairs(init):
    """Extract verb/object rows from legacy GAM's ProcessGAMCommand if-chains.

    Commands before the 'users = getUsersToModify()' line are gam <verb> ...;
    the chain after it is gam <users> <verb> ....
    """
    tree = ast.parse(init.read_text(encoding='utf-8'))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'ProcessGAMCommand')
    body = next(n for n in func.body if isinstance(n, ast.Try)).body
    split = next(i for i, s in enumerate(body)
                 if isinstance(s, ast.Assign) and 'getUsersToModify' in ast.unparse(s.value))
    rows = []
    _walk_legacy(body[:split], None, None, 'main', rows)
    _walk_legacy(body[split:], None, None, 'user', rows)
    # gam calendar|course|oauth <x> <subcommand>: the walker records these as
    # verb=calendar, object=subcommand. Re-home them on the GAM7 scope names so
    # the versions compare like for like.
    scoped = {'calendar': 'calendar', 'course': 'course', 'class': 'course', 'oauth': 'oauth', 'oauth2': 'oauth'}
    for row in rows:
        if row[0] == 'main' and row[1] in scoped and row[2]:
            row[0], row[1], row[2] = scoped[row[1]], row[2], None
    return rows


def legacy_version(src):
    """Read GAM_VERSION / gam_version from a legacy tree without importing it."""
    for path in [src / 'var.py', src / '__init__.py']:
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '').lower() in ('gam_version', '__version__'):
                if isinstance(node.value, ast.Constant):
                    return node.value.value
    raise SystemExit('legacy version string not found')


def wiki_pages(wiki_dir, gam7_json):
    """Map each GAM7 command ('scope verb object') to the wiki page documenting its syntax.

    Only syntax lines count (they carry <placeholders> or [options]); worked
    examples appear on many pages. GamUpdates.md is a changelog, so it is skipped.
    When several pages document a command, the one with the most syntax lines wins.
    """
    from collections import Counter, defaultdict
    g7 = json.loads(Path(gam7_json).read_text(encoding='utf-8'))
    t = g7['tables']
    known = {' '.join(p for p in (s, v, o) if p) for s, v, o, _, _ in g7['pairs']}
    scopes = {
        'user': (t['USER_COMMANDS_ALIASES'], t['USER_COMMANDS_OBJ_ALIASES']),
        'cros': ({}, t['CROS_COMMANDS_OBJ_ALIASES']),
        'main': ({}, t['MAIN_COMMANDS_OBJ_ALIASES']),
    }
    hits = defaultdict(Counter)
    for page in sorted(Path(wiki_dir).glob('*.md')):
        if page.stem == 'GamUpdates':
            continue
        for line in page.read_text(encoding='utf-8', errors='replace').splitlines():
            words = line.split()
            if len(words) < 2 or words[0] != 'gam' or not any(c in line for c in '<['):
                continue
            head = words[1]
            if head == '<UserTypeEntity>':
                forms = [('user', words[2:])]
            elif head == '[<UserTypeEntity>]':
                # optional entity: the command exists with and without a user in front
                forms = [('user', words[2:]), ('main', words[2:])]
            elif head == '<CrOSTypeEntity>':
                forms = [('cros', words[2:])]
            elif set(head.split('|')) & {'calendar', 'calendars', 'course', 'courses', 'resource', 'resources'}:
                sub = head.split('|')[0].rstrip('s')
                forms = [(sub, words[3:])]
            elif head.startswith('<') or head.startswith('['):
                continue
            else:
                forms = [('main', words[1:])]
            for scope, rest in forms:
                valiases, oaliases = scopes.get(scope, ({}, {}))
                verbs = rest[0].split('|') if rest else []
                objs = rest[1].split('|') if len(rest) > 1 else ['']
                for v in verbs:
                    v = valiases.get(v, v)
                    for o in objs:
                        o = oaliases.get(o, o).replace('_', '')
                        o = o[:-1] if o.endswith('s') and f'{scope} {v} {o[:-1]}' in known else o
                        for key in (f'{scope} {v} {o}'.strip(), f'{scope} {v}'):
                            if key in known:
                                hits[key][page.stem] += 1
                                break
    return {k: 'https://github.com/GAM-team/GAM/wiki/' + c.most_common(1)[0][0] for k, c in sorted(hits.items())}


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--wiki':
        # python3 build_verb_table.py --wiki GAM.wiki verbs/gam7.json > verbs/wiki.json
        pages = wiki_pages(sys.argv[2], sys.argv[3])
        json.dump({'source': 'https://github.com/GAM-team/GAM/wiki', 'pages': pages}, sys.stdout, indent=1)
        sys.stdout.write('\n')
        return
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    init = src / '__init__.py'
    if not (src / 'gamlib' / 'glclargs.py').exists():
        rows = legacy_pairs(init)
        if len(rows) < 100:
            raise SystemExit(f'Only {len(rows)} verb rows found; the legacy dispatcher has changed shape.')
        out = {'gam_version': legacy_version(src), 'dialect': 'legacy', 'pairs': rows}
        json.dump(out, sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write('\n')
        return
    cmd_all = class_constants(src / 'gamlib' / 'glclargs.py', 'GamCLArgs')
    missing = [a for a in CMD_ATTRS if a not in cmd_all]
    if missing:
        raise SystemExit(f'Cmd attributes not found: {missing}')
    tables = module_tables(init, INIT_TABLES, cmd_all)
    out = {
        'gam_version': gam_version(init),
        'dialect': 'modern',
        'tables': tables,
        'pairs': modern_pairs(tables),
        'cmd': {a: cmd_all[a] for a in CMD_ATTRS},
        'config_variables': config_variable_names(src / 'gamlib' / 'glcfg.py'),
    }
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
