from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pim_api
import tensorflow as tf
import pim_tf as tf_pim_ops


tf.debugging.set_log_device_placement(True)

class PimAddTestConstant(tf.test.TestCase):
    def test_vector_vector(self):
      with tf.device('/GPU:0'):
        input0 = tf.constant([1]*32, dtype=tf.float16)
        input1 = tf.constant([2]*32, dtype=tf.float16)
        add = tf.constant([0], dtype=tf.int32)
        result = None
        with self.test_session():
            result = tf_pim_ops.pim_eltwise(input0, input1, add)
            self.assertAllEqual(result, [3]*32)
            print(result)

if __name__ == '__main__':
    #pim_api.PimInitialize(pim_api.RT_TYPE_HIP, pim_api.PIM_FP16)
    tf_pim_ops.pim_init()
    tf.test.main()
    tf_pim_ops.pim_deinit()

