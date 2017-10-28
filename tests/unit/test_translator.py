import ast
import unittest
from translator import Translator, STDLIB


class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.translator = Translator()

    def test_translate_Module(self):
        res1 = self.translator._translate_Module(ast.Module())
        res2 = self.translator._translate_Module(ast.Module(body=[]))
        self.assertEqual(res1, 'local M = {}\n' + STDLIB + '\nreturn M\n')
        self.assertEqual(res2, 'local M = {}\n'+ STDLIB + '\nreturn M\n')

    def test_translate_Assign(self):
        ast1 = ast.Assign(targets=[ast.Name(id='x', ctx=ast.Store())], value=ast.Num(n=2))
        ast2 = ast.Assign(targets=[ast.Name(id='x', ctx=ast.Store()), ast.Name(id='y', ctx=ast.Store())], value=ast.Num(n=2))
        ast3 = ast.Assign(targets=[ast.Name(id='x', ctx=ast.Store())], value=ast.Name(id='z', ctx=ast.Load()))
        res1 = self.translator._translate_Assign(ast1)
        res2 = self.translator._translate_Assign(ast2)
        res3 = self.translator._translate_Assign(ast3)
        self.assertEqual(res1, 'local x=2')
        self.assertEqual(res2, 'local x,y=2,2')
        self.assertEqual(res3, 'local x=z')

    def test_translate_Str(self):
        res = self.translator._translate_Str(ast.Str(s='string'))
        self.assertEqual(res, '"string"')

    def test_translate_Bytes(self):
        res = self.translator._translate_Str(ast.Bytes(s='string'))
        self.assertEqual(res, '"string"')

    def test_translate_Num(self):
        res = self.translator._translate_Num(ast.Num(n=123))
        self.assertEqual(res, '123')

    def test_translate_BinOp_simple(self):
        add_stmt = ast.BinOp(left=ast.Name(id='x', ctx=ast.Load()), op=ast.Add(), right=ast.Num(n=5))
        sub_stmt = ast.BinOp(left=ast.Name(id='y', ctx=ast.Load()), op=ast.Sub(), right=ast.Num(n=3))
        mult_stmt = ast.BinOp(left=ast.Num(n=3), op=ast.Mult(), right=ast.Name(id='z', ctx=ast.Load()))
        res1 = self.translator._translate_BinOp(ast.BinOp(left=add_stmt, op=ast.Add(), right=sub_stmt))
        res2 = self.translator._translate_BinOp(ast.BinOp(left=mult_stmt, op=ast.Add(), right=sub_stmt))
        res3 = self.translator._translate_BinOp(ast.BinOp(left=ast.Str(s='s1'), op=ast.Add(), right=ast.Str(s='s2')))
        self.assertEqual(res1, '_add_op(_add_op(x,5),(y-3))')
        self.assertEqual(res2, '_add_op((3*z),(y-3))')
        self.assertEqual(res3, '_add_op("s1","s2")')

    def test_translate_BinOp_bit_ops(self):
        lshift_stmt = ast.LShift(left=ast.Name(id='x', ctx=ast.Load()), op=ast.LShift(), right=ast.Num(n=5))
        rshift_stmt = ast.RShift(left=ast.Name(id='x', ctx=ast.Load()), op=ast.RShift(), right=ast.Num(n=5))
        or_stmt = ast.BitOr(left=ast.Name(id='x', ctx=ast.Load()), op=ast.BitOr(), right=ast.Num(n=5))
        xor_stmt = ast.BitXor(left=ast.Name(id='x', ctx=ast.Load()), op=ast.BitXor(), right=ast.Num(n=5))
        and_stmt = ast.BitAnd(left=ast.Name(id='x', ctx=ast.Load()), op=ast.BitAnd(), right=ast.Num(n=5))
        res1 = self.translator._translate_BinOp(lshift_stmt)
        res2 = self.translator._translate_BinOp(rshift_stmt)
        res3 = self.translator._translate_BinOp(or_stmt)
        res4 = self.translator._translate_BinOp(xor_stmt)
        res5 = self.translator._translate_BinOp(and_stmt)
        self.assertEqual(res1, 'bit.lshift(x,5)')
        self.assertEqual(res2, 'bit.rshift(x,5)')
        self.assertEqual(res3, 'bit.bor(x,5)')
        self.assertEqual(res4, 'bit.bxor(x,5)')
        self.assertEqual(res5, 'bit.band(x,5)')

    def test_translate_BinOp_strings(self):
        stmt1 = ast.BinOp(left=ast.Str(s="s1"), op=ast.Mult(), right=ast.Num(n=4))
        stmt2 = ast.BinOp(left=ast.Str(s="s2"), op=ast.Mult(), right=ast.Name(id='x'))
        res1 = self.translator._translate_BinOp(stmt1)
        res2 = self.translator._translate_BinOp(stmt2)
        self.assertEqual(res1, 'string.rep("s1",4)')
        self.assertEqual(res2, 'string.rep("s2",x)')
    
    def test_translate_Compare(self):
        ast1 = ast.Compare(
            left=ast.Num(n=12), 
            ops=[ast.Gt(), ast.Gt()], 
            comparators=[ast.Name(id='z', ctx=ast.Load()), ast.Num(n=11)]
        )
        ast2 = ast.Compare(
            left=ast.Name(id='z', ctx=ast.Load()), 
            ops=[ast.Gt()], 
            comparators=[ast.Num(n=12)]
        )
        ast3 = ast.Compare(
            left=ast.Num(n=0), 
            ops=[ast.Lt(), ast.Lt(), ast.Lt()], 
            comparators=[ast.Name(id='x', ctx=ast.Load()), ast.Name(id='y', ctx=ast.Load()), ast.Num(n=12)]
        )
        res1 = self.translator._translate_Compare(ast1)
        res2 = self.translator._translate_Compare(ast2)
        res3 = self.translator._translate_Compare(ast3)
        self.assertEqual(res1, '(12>z and z>11)')
        self.assertEqual(res2, '(z>12)')
        self.assertEqual(res3, '(0<x and x<y and y<12)')
    
    def test_translate_BoolOp(self):
        ast1 = ast.BoolOp(
            op=ast.Or(), 
            values=[
                ast.Compare(left=ast.Name(id='z', ctx=ast.Load()), ops=[ast.Gt()], comparators=[ast.Num(n=12)]), 
                ast.Compare(left=ast.Name(id='z', ctx=ast.Load()), ops=[ast.LtE()], comparators=[ast.Num(n=15)])
            ]
        )
        ast2 = ast.BoolOp(
            op=ast.And(), 
            values=[
                ast.Compare(left=ast.Name(id='z', ctx=ast.Load()), ops=[ast.Gt()], comparators=[ast.Num(n=12)]), 
                ast.Compare(left=ast.Name(id='z', ctx=ast.Load()), ops=[ast.LtE()], comparators=[ast.Num(n=15)])
            ]
        )
        ast3 = ast.BoolOp(
            op=ast.And(), 
            values=[
                ast.Compare(left=ast.Name(id='z', ctx=ast.Load()), ops=[ast.Gt()], comparators=[ast.Num(n=12)]), 
                ast.Compare(left=ast.Name(id='z', ctx=ast.Load()), ops=[ast.LtE()], comparators=[ast.Num(n=15)]),
                ast.Compare(left=ast.Name(id='y', ctx=ast.Load()), ops=[ast.LtE()], comparators=[ast.Num(n=25)])
            ]
        )
        res1 = self.translator._translate_BoolOp(ast1)
        res2 = self.translator._translate_BoolOp(ast2)
        res3 = self.translator._translate_BoolOp(ast3)
        self.assertEqual(res1, '((z>12) or (z<=15))')
        self.assertEqual(res2, '((z>12) and (z<=15))')
        self.assertEqual(res3, '((z>12) and (z<=15) and (y<=25))')


suite = unittest.TestLoader().loadTestsFromTestCase(TestTranslator)


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite)
