import logging

import tvm.ir
from tvm.relay import transform
from tvm.relay.build_module import bind_params_by_name

from ...dataflow_pattern import wildcard, is_op
from .register import register_pattern_table

logger = logging.getLogger("Buda")

def _register_external_op_helper(op_name, supported=True):
    @tvm.ir.register_op_attr(op_name, "target.buda")
    def _func_wrapper(expr):
        return supported
    return _func_wrapper

# _register_external_op_helper("nn.dense")
_register_external_op_helper("add")
_register_external_op_helper("subtract")
_register_external_op_helper("multiply")

def dense_to_matmul():
  data = wildcard()
  weight = wildcard()
  weight_t = is_op('transpose')(weight)
  return is_op('nn.dense')(weight_t, data)

@register_pattern_table("buda")
def pattern_table():
  matmul = ("buda.matmul", dense_to_matmul())
  buda_patterns = [matmul]
  return buda_patterns

from tvm.relay.dataflow_pattern import *
class DenseWeightTranspose(DFPatternCallback):
    def __init__(self):
        super().__init__()
        self.weight = wildcard()
        act = wildcard()
        #self.opt_t = weight.optional(lambda x: is_op('transpose')(x))
        #self.pattern = is_op('nn.dense')(act, self.opt_t)
        self.pattern = is_op('nn.dense')(act, self.weight)
        self.transpose_pattern = is_op('transpose')(wildcard())

    def callback(self, pre, post, node_map):
        # print("match:")
        # print("PRE", pre)
        # print("POST", post)
        # print("NODE_MAP", node_map)

        #t = node_map[self.opt_t][0]
        #print("Transpose: ", t)
        # print(type(pre))
        # print(type(post))
        if self.transpose_pattern.match(pre.args[0]):
            print("has transpose")
            return post

        # Doesn't have transpose, add it
        print("doesn't have transpose")
        weight = pre.args[0]
        act = pre.args[1]
        wt1 = tvm.relay.transpose(weight)
        wt2 = tvm.relay.transpose(wt1)
        return tvm.relay.nn.dense(wt2, act)

def partition_for_buda(mod):
    seq1 = tvm.transform.Sequential(
        [
            # tvm.transform.PrintIR(),
            transform.CanonicalizeOps(),
            # tvm.transform.PrintIR(),
            # transform.InferType(),
            # tvm.transform.PrintIR(),
            # transform.SimplifyInference(),
            # tvm.transform.PrintIR(),
            # transform.FoldConstant(),
            # tvm.transform.PrintIR(),
            # transform.FoldScaleAxis(),
            # tvm.transform.PrintIR(),
            # # fold consecutive add ops to simplify pattern `conv2d-bias_add-bn-relu`
            # transform.SimplifyExpr(),
            # tvm.transform.PrintIR(),
            # transform.FoldConstant(),
            # tvm.transform.PrintIR(),
        ]
    )
    seq2 = tvm.transform.Sequential(
        [
            tvm.transform.PrintIR(),
            transform.MergeComposite(pattern_table()),
            transform.FoldConstant(),
            tvm.transform.PrintIR(),
            transform.AnnotateTarget("buda"),
            tvm.transform.PrintIR(),
            transform.MergeCompilerRegions(),
            tvm.transform.PrintIR(),
            transform.PartitionGraph(),
            tvm.transform.PrintIR(),
            tvm.transform.PrintIR(),
        ]
    )
    with tvm.transform.PassContext(opt_level=3):
        mod = seq1(mod)
        mod["main"] = rewrite(DenseWeightTranspose(), mod["main"])
        mod = seq2(mod)
    return mod