import ast
import operator
from functools import reduce


STDLIB = """
local function _add_op(a, b)
    if type(a) == "string" then
        return a .. b
    else
        return a + b
    end
end

function list(...)
    local lst = {}
  
    function lst.append(elt)
        table.insert(lst, elt)
    end

    function lst.iter()
        i = -1
        return function()
            i = i + 1
            local v = lst[i]
            if v then
                return v
            end
        end, lst, 0
    end

    for i, v in ipairs({...}) do
        lst[i - 1] = v
    end

    return lst
end


function range(...)
    local lst = list()
    args = {...}
    if #args == 1 then
        start = 0
        end_ = args[1]
        step = 1
    elseif #args == 2 then
        start = args[1]
        end_ = args[2]
        step = 1
    else
        start = args[1]
        end_ = args[2]
        step = args[3]
    end

    for i=start, end_, step do
        lst.append(i)
    end

    return lst
end

"""
TAB_SPACES = 4


class TranslatorException(Exception):
    """
    Base translator exception
    """


class InvalidBinOp(TranslatorException):
    """
    Indicates invalid binary operation
    """


def indent(func):
    def wrapper(*args, **kwargs):
        indent_level = kwargs.get('indent_level', 0)
        kwargs['indent_level'] = 0
        return ' ' * indent_level * TAB_SPACES + func(*args, **kwargs)

    return wrapper


class Env:
    __slots__ = ('namespace', '_maps', 'parent', 'child', 'globals')

    def __init__(self, namespace=''):
        self.namespace = namespace
        self._maps = {}
        self.globals = set()
        self.child = None
        self.parent = None

    def set(self, name, val):
        self._maps[name] = val

    def get(self, name):
        return self._maps.get(name, None)

    def add_child(self, env):
        self.child = env
        env.parent = self


class Translator:
    def __init__(self, out_file=None):
        self._out = out_file

    def _output_line(self, line):
        return line + '\n'

    def _out_fmt(self, *args, delimiter=''):
        fmt_str = delimiter.join(['{}' for _ in args])
        return fmt_str.format(*args)

    def _translate_Module(self, tree, **kwargs):
        env = Env(namespace='M')
        mod_begin = self._output_line("local M = {}")
        try:
            body = tree.body
        except AttributeError:
            body = []
        mod_body = self._output_line(
            reduce(
                lambda a, v: a + self.visit(v, module_prefix="M", env=env), 
                body, ""
            )
        )
        mod_end = self._output_line("return M")
        return self._out_fmt(mod_begin, STDLIB, mod_body, mod_end)

    def _translate_Global(self, tree, **kwargs):
        env = kwargs.get('env', Env())
        env.globals = set(tree.names)
        return ''

    @indent
    def _translate_Assign(self, tree, **kwargs):
        non_local = kwargs.get('non_local', False)
        var_names = [t.id for t in tree.targets]
        global_ = bool(set(var_names).intersection(kwargs.get('env', Env()).globals))
        targets = ','.join(var_names)
        values = ','.join([self.visit(tree.value, **kwargs) for _ in tree.targets])
        return self._out_fmt('local ' if not non_local and not global_ else '', targets, '=', values)

    @indent
    def _translate_Return(self, tree, **kwargs):
        return self._out_fmt('return ' + self.visit(tree.value, **kwargs))

    @indent
    def _translate_Num(self, tree, **kwargs):
        return str(tree.n)

    @indent
    def _translate_Str(self, tree, **kwargs):
        return '"' + tree.s + '"'
    _translate_Bytes = _translate_Str

    @indent
    def _translate_Name(self, tree, **kwargs):
        return tree.id

    def _op_Add(self, left, right):
        return '_add_op(' + left + ',' + right + ')'

    def _op_LShift(self, left, right):
        return 'bit.lshift(' + left + ',' + right + ')'
    
    def _op_RShift(self, left, right):
        return 'bit.rshift(' + left + ',' + right + ')'

    def _op_BitOr(self, left, right):
        return 'bit.bor(' + left + ',' + right + ')'
    
    def _op_BitXor(self, left, right):
        return 'bit.bxor(' + left + ',' + right + ')'
    
    def _op_BitAnd(self, left, right):
        return 'bit.band(' + left + ',' + right + ')'

    def _op_Eq(self):
        return '=='
    
    def _op_NotEq(self):
        return '!='
    
    def _op_Gt(self):
        return '>'

    def _op_GtE(self):
        return '>='
    
    def _op_Lt(self):
        return '<'

    def _op_LtE(self):
        return '<='

    def _op_Or(self):
        return 'or'

    def _op_And(self):
        return 'and'

    def _translate_BoolOp(self, tree, **kwargs):
        op_meth = getattr(self, '_op_{}'.format(tree.op.__class__.__name__), None)
        if op_meth:
            return '(' + (' ' + op_meth() + ' ').join([self.visit(v, **kwargs) for v in tree.values]) + ')'

    def _translate_Expr(self, tree, **kwargs):
        return self.visit(tree.value, **kwargs)

    @indent
    def _translate_Call(self, tree, **kwargs):
        args = ','.join([self.visit(a, **kwargs) for a in tree.args])
        cur_env = kwargs.get('env', None)
        arg_list = '(' + args + ')'
        if isinstance(tree.func, ast.Name) and cur_env:
            real_name = cur_env.get(tree.func.id)
            while real_name is None and cur_env.parent:
                cur_env = cur_env.parent
                real_name = cur_env.get(tree.func.id)

            return self._output_line((tree.func.id if real_name is None else real_name) + arg_list)
        else:
            return self.visit(tree.func, **kwargs) + arg_list

    def _translate_Compare(self, tree, **kwargs):
        def op_to_str(op):
            op_meth = getattr(self, '_op_{}'.format(op.__class__.__name__), None)
            if op_meth:
                return op_meth()

        cond = []
        last_comp = self.visit(tree.left, **kwargs)
        for op, comp in zip(tree.ops, tree.comparators):
            cond.append(last_comp + op_to_str(op) + self.visit(comp, **kwargs)) 
            last_comp = self.visit(comp, **kwargs)
        return '(' + ' and '.join(cond) + ')'

    def _translate_FunctionDef(self, tree, **kwargs):
        env = kwargs.get('env', Env())
        indent_level = kwargs.get('indent_level', 0)
        indent = ' ' * indent_level * TAB_SPACES
        func_args = ', '.join([a.arg for a in tree.args.args])
        real_name = tree.name
        func_namespace = env.namespace
        for dec in tree.decorator_list:
            if isinstance(dec.func, ast.Name) and dec.func.id == 'ns':
                func_namespace = dec.args[0].s
                break
        if func_namespace:
            real_name = self._out_fmt(func_namespace + '.', tree.name)
            func_begin = indent + "function {}({})\n".format(real_name, func_args)
        else:
            func_begin = indent + "local function {}({})\n".format(real_name, func_args)
        kwargs['indent_level'] = indent_level + 1
        kwargs['non_local'] = False
        env.set(tree.name, real_name)
        env.add_child(Env())
        kwargs['env'] = env.child
        func_body = reduce(lambda a, v: a + (self.visit(v, **kwargs) + '\n'), tree.body, "")
        func_end = indent + "end\n"
        return self._output_line(self._out_fmt(func_begin, func_body, func_end))

    def _translate_If(self, tree, **kwargs):
        indent_level = kwargs.get('indent_level', 0)
        indent = ' ' * indent_level * TAB_SPACES
        if_begin = indent + 'if ' + self.visit(tree.test) + ' then\n'
        kwargs['indent_level'] = indent_level + 1
        kwargs['non_local'] = True
        if_body = reduce(lambda a, v: a + (self.visit(v, **kwargs) + '\n'), tree.body, "")
        if_orelse = ''
        if tree.orelse:
            orelse_body = reduce(lambda a, v: a + (self.visit(v, **kwargs) + '\n'), tree.orelse, "")
            if_orelse = indent + 'else\n' + orelse_body
        if_end = indent + 'end'
        return self._out_fmt(if_begin, if_body, if_orelse, if_end)

    @indent
    def _translate_BinOp(self, tree, **kwargs):
        ops_map = {
            ast.Sub: '-',
            ast.Mult: '*',
            ast.Div: '/',
            ast.Mod: '%',
            ast.Pow: '^',
            ast.FloorDiv: '//'
        }
        simple_stmts = (ast.Num, ast.Str, ast.Bytes)
        op = ops_map.get(tree.op.__class__, None)
        op_meth = getattr(self, '_op_{}'.format(tree.op.__class__.__name__), None)
        left = self.visit(tree.left, **kwargs)
        right = self.visit(tree.right, **kwargs)
        if op:
            if tree.left.__class__ in (ast.Str, ast.Bytes) and tree.right.__class__ in (ast.Num, ast.Name):
                return 'string.rep(' + left + ',' + right + ')'
            elif (tree.left.__class__ in simple_stmts) and (tree.right.__class__ in simple_stmts) and tree.left.__class__ != tree.right.__class__:
                raise TypeError("unsupported operand types for {}".format(op))
            else:
                return '(' + left + op + right + ')'
        elif op_meth is not None:
            return op_meth(left, right)
        else:
            raise InvalidBinOp("Invalid binary operation: {}".format(tree.op.__class__.__name__))

    def _translate_NoneType(self, tree, **kwargs):
        return 'nil'

    @indent
    def _translate_Attribute(self, tree, **kwargs):
        return '(' + self.visit(tree.value, **kwargs) + '.' + tree.attr + ')'

    @indent
    def _translate_Import(self, tree, **kwargs):
        return self._output_line('\n'.join([self.visit(n, **kwargs) for n in tree.names]))

    @indent
    def _translate_ImportFrom(self, tree, **kwargs):
        kwargs['from_mod'] = tree.module
        return self._output_line('\n'.join([self.visit(n, **kwargs) for n in tree.names]))

    @indent
    def _translate_List(self, tree, **kwargs):
        elts = ','.join([self.visit(elt, **kwargs) for elt in tree.elts])
        return 'list(' + elts + ')'
    
    @indent
    def _translate_Dict(self, tree, **kwargs):
        items = ','.join([
            self.visit(k, **kwargs) + ':' + self.visit(v, **kwargs) 
            for k, v in zip(tree.keys, tree.values)
        ])
        return '{' + items + '}'

    @indent
    def _translate_Subscript(self, tree, **kwargs):
        return self.visit(tree.value, **kwargs) + '[' + self.visit(tree.slice, **kwargs) + ']'
    
    @indent
    def _translate_Index(self, tree, **kwargs):
        return self.visit(tree.value, **kwargs)

    @indent
    def _translate_alias(self, tree, **kwargs):
        from_mod = kwargs.get('from_mod', None)
        asname = tree.asname if tree.asname is not None else tree.name
        if from_mod:
            return asname + '=require("' + from_mod + '").' + tree.name
        else:
            return asname + '=require("' + tree.name + '")'

    def _translate_For(self, tree, **kwargs):
        indent_level = kwargs.get('indent_level', 0)
        indent = ' ' * indent_level * TAB_SPACES
        kwargs['indent_level'] = indent_level + 1
        for_body = reduce(lambda a, v: a + (self.visit(v, **kwargs) + '\n'), tree.body, "")
        kwargs['indent_level'] = 0
        target = self.visit(tree.target, **kwargs)
        iter_ = self.visit(tree.iter, **kwargs)
        for_begin = indent + 'for ' + target + ' in (' + iter_ + ').iter() do\n'
        for_end = indent + 'end\n'
        return self._out_fmt(for_begin, for_body, for_end)

    def visit(self, tree, **kwargs):
        parse_meth = getattr(self, '_translate_{}'.format(tree.__class__.__name__))
        if parse_meth:
            return parse_meth(tree, **kwargs)

    def translate(self, source, **kwargs):
        tree = ast.parse(source)
        tree_str = self.visit(tree)
        if self._out:
            with open(self._out, 'w') as out:
                out.write(tree_str)
        else:
            return tree_str
