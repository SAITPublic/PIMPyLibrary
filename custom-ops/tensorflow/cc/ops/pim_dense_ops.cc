/*
 * Copyright (C) 2021 Samsung Electronics Co. LTD
 *
 * This software is a property of Samsung Electronics.
 * No part of this software, either material or conceptual may be copied or distributed, transmitted,
 * transcribed, stored in a retrieval system or translated into any human or computer language in any form by any means,
 * electronic, mechanical, manual or otherwise, or disclosed
 * to third parties without the express written permission of Samsung Electronics.
 */

#include <iostream>
#include "tensorflow/core/framework/op.h"
#include "tensorflow/core/framework/op_kernel.h"

using namespace tensorflow;  // NOLINT(build/namespaces)

// Todo: How to create new ShapeHandle and pass to c->set_output()
REGISTER_OP("PimDense")
    .Input("first: float16")  //input
    .Input("second: float16") //weight
    .Input("third: float16")  //bias
    .Input("fourth: int32")   //has_bias
    .Output("ans: float16")
    .SetShapeFn([](::tensorflow::shape_inference::InferenceContext* c) {
        // shape_inference::ShapeHandle out_shape;
        // out_shape = c->MakeShape({1});
        // TF_RETURN_IF_ERROR(c->Subshape(c->input(0),0 ,0 , &out_shape));
        // std::cout << "out shape " << out_shape(0) << std::endl;
        // c->set_output(0,c->UnknownShape());
        // c->set_output(0,out_shape);
        // c->set_output(0, c->input(0));
        return Status::OK();
    });
