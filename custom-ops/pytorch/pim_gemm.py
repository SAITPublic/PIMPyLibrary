import torch
import torch.nn as nn
from torch.autograd import Function
import pim_api

class PimGemmFunction(Function):
    @staticmethod
    def forward(ctx, inputs, weights, bias, act, block):

        input_dims = inputs.ndim
        if inputs.ndim not in [3,4]:
            print("Input dimension not supported in Gemm")
            return

        if weights.ndim not in [2,3]:
            print("Only 2D and 3D weights supported")
            return

        if weights.ndim == 2:
             weights = torch.unsqueeze(weights,0)
        if inputs.ndim == 3:
             inputs = torch.unsqueeze(inputs,0)

        in_w = weights.size()[1]
        out_w = weights.size()[2]
        num_batch = inputs.size()[0]
        num_channels = inputs.size()[1]
        inout_h = inputs.size()[2]

        if input_dims == 4:
            out_tensor = torch.empty(
                (num_batch, num_channels, inout_h, out_w), dtype=torch.float16, device=inputs.device)
        else:
            out_tensor = torch.empty(
                (num_channels, inout_h, out_w), dtype=torch.float16, device=inputs.device)

        #print('Custom op pimgemm descriptor (n, c, inout_h, in_w, out_w)', num_batch, num_channels, inout_h, in_w, out_w)
        pim_gemm_desc = pim_api.PimCreateGemmDesc(num_batch, num_channels, inout_h, in_w, out_w, pim_api.PIM_FP16)
        device_input = pim_api.PimCreateBo(pim_gemm_desc, pim_api.MEM_TYPE_DEVICE, pim_api.GEMM_INPUT, inputs.data_ptr())
        device_weight = pim_api.PimCreateBo(pim_gemm_desc, pim_api.MEM_TYPE_DEVICE, pim_api.GEMM_WEIGHT, weights.data_ptr())
        device_bias = pim_api.PimCreateBo(pim_gemm_desc, pim_api.MEM_TYPE_DEVICE, pim_api.GEMM_BIAS, bias.data_ptr())
        device_output = pim_api.PimCreateBo(pim_gemm_desc, pim_api.MEM_TYPE_DEVICE, pim_api.GEMM_OUTPUT, out_tensor.data_ptr())
        pim_api.PimExecuteGemm(device_output, device_input, device_weight, device_bias, act, None, block)

        pim_api.PimDestroyBo(device_input)
        pim_api.PimDestroyBo(device_weight)
        pim_api.PimDestroyBo(device_bias)
        pim_api.PimDestroyBo(device_output)
        pim_api.PimDestroyGemmDesc(pim_gemm_desc)

        return out_tensor

    @staticmethod
    def backward(ctx, grad_out):
        raise NotImplementedError

class PimGemm(nn.Module):

    def __init__(self,device=None, dtype=None) -> None:
        super(PimGemm, self).__init__()

    def reset_parameters(self) -> None:
        super(PimGemm, self).reset_parameters()

    def __repr__(self):
        return "PIM Gemm layer"

    def forward(self, inputs, weight, bias, act, block):
        return PimPimGemmFunction.apply(inputs, weight, bias, act, block)
