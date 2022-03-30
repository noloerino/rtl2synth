
import random
import os

import pycvc5

from easyila.lynth import smt
from easyila.lynth.oracleinterface import *

class TestSygus:
    """
    Sanity checks that SMT and sygus functions work
    """

    def test_from_cvc5(self):
        c_slv = pycvc5.Solver()
        c_slv.setOption("lang", "sygus2")
        c_slv.setOption("incremental", "false")
        c_slv.setLogic("BV")
        bv32 = c_slv.mkBitVectorSort(32)
        x = c_slv.mkVar(bv32, "x")
        y = c_slv.mkVar(bv32, "y")
        start = c_slv.mkVar(bv32, "start")
        c_add = c_slv.mkTerm(pycvc5.Kind.BVAdd, [x, y])
        # the Python API seems not not expose the correct mkTerm call to create a Term with kind
        # Lambda, so we just do a really dumb sygus call instead
        g = c_slv.mkSygusGrammar([x, y], [start])
        g.addRules(start, {c_add})
        g.addAnyVariable(start)
        sfn = c_slv.synthFun("fn", [x, y], bv32, g)
        assert c_slv.checkSynth().isUnsat()
        actual = c_slv.getSynthSolutions([sfn])[0]
        expected = smt.LambdaTerm(
            (smt.Variable("x", smt.BVSort(32)), smt.Variable("y", smt.BVSort(32))),
            smt.OpTerm(
                smt.Kind.BVAdd,
                (smt.Variable("x", smt.BVSort(32)), smt.Variable("y", smt.BVSort(32))),
            ),
        )
        assert smt.LambdaTerm.from_cvc5(actual) == expected

    def test_lambda_sort(self):
        """
        Tests that LambdaTerms have the correct sort.
        Note that this does NOT test type checking.
        """
        bv32 = smt.BVSort(32)
        lt = smt.LambdaTerm(
            (smt.Variable("x", bv32), smt.Variable("y", bv32)),
            smt.OpTerm(smt.Kind.BVAdd, (smt.Variable("x", bv32), smt.Variable("y", bv32)))
        )
        assert lt.sort == smt.FunctionSort((bv32, bv32), bv32)

    def test_quant_sort(self):
        bv32 = smt.BVSort(32)
        x = smt.Variable("x", bv32)
        e = smt.QuantTerm(smt.Kind.Exists, (x,), smt.OpTerm(smt.Kind.Equal, (x, smt.BVConst(0, 32))))
        assert e.sort == smt.BoolSort()

    def test_to_uclid(self):
        # TODO convert to uclid python library
        bv32 = smt.BVSort(32)
        lt = smt.LambdaTerm(
            (smt.Variable("x", bv32), smt.Variable("y", bv32)),
            smt.OpTerm(smt.Kind.BVAdd, (smt.Variable("x", bv32), smt.Variable("y", bv32)))
        )
        expected = "(define-fun ((x (_ BitVec 32)) (y (_ BitVec 32))) (_ BitVec 32) (bvadd x y))"
        assert lt.to_uclid() == expected

    def test_new_solver_no_exceptions(self):
        bv32 = smt.BVSort(32)
        x = smt.Variable("x", bv32)
        y = smt.Variable("y", bv32)
        start = smt.Variable("start", bv32)
        addbv = smt.OpTerm(smt.Kind.BVAdd, (start, start))
        subbv = smt.OpTerm(smt.Kind.BVSub, (start, start))
        orbv = smt.OpTerm(smt.Kind.BVOr, (start, start))
        solver = smt.SynthFun(
            "alu_add",
            (x, y),
            bv32,
            smt.Grammar(
                bound_vars=(x, y),
                input_vars=(start,),
                terms={start: (addbv, subbv, orbv),},
            )
        ).new_solver()

    def test_io_oracle_replay(self, tmpdir):
        random.seed(0)
        log_path = os.path.join(tmpdir, "log")
        def dummy_io_fun(_args=None):
            return random.randint(0, 100)
        o0 = IOOracle("io0", [32, 32], 32, dummy_io_fun, log_path=log_path)
        callcount = 10
        for _ in range(callcount):
            o0.invoke([dummy_io_fun(), dummy_io_fun()])
        expected_inputs = [c.inputs for c in o0.calls]
        assert len(expected_inputs) == 10
        o0.save_call_logs()
        o1 = IOOracle.from_call_logs("io1", [32, 32], 32, dummy_io_fun, log_path)
        for _ in range(callcount):
            o1.invoke(o1.next_replay_input())
        actual_inputs = [c.inputs for c in o1.calls]
        assert expected_inputs == actual_inputs