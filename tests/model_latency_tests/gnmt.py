import tensorflow as tf
from tabulate import tabulate
import time
import timeit
import os
import numpy as np

SEED = 1234
# GNMT model configuration
HIDDEN_SIZE = 1024
EMBEDDING_DIM = 1024
VOCAB_SIZE = 32000
# Performance table for different layers
eval_time = []
args = []
dtype = tf.float16

lstm_kernel_initializer = tf.keras.initializers.RandomNormal(seed=SEED,mean=0.2,stddev=0.8)

# Encoder class GNMT model
class Encoder(tf.keras.Model):
  def __init__(self, vocab_size, embedding_dim, enc_units, batch_sz, initializer, dtype):
    super(Encoder, self).__init__()

    self.batch_sz = batch_sz
    self.enc_units = enc_units
    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)

    self.lstm1 = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(enc_units,
                           kernel_initializer=lstm_kernel_initializer,
                           recurrent_initializer=lstm_kernel_initializer,
                           return_sequences=True,
                           dtype=dtype,
                           trainable=False))
    self.lstm2 = tf.keras.layers.LSTM(enc_units,
                           kernel_initializer=lstm_kernel_initializer,
                           recurrent_initializer=lstm_kernel_initializer,
                           return_sequences=True,
                           dtype=dtype,
                           trainable=False)
    self.lstm3 = tf.keras.layers.LSTM(enc_units,
                           kernel_initializer=lstm_kernel_initializer,
                           recurrent_initializer=lstm_kernel_initializer,
                           return_sequences=True,
                           dtype=dtype,
                           trainable=False)
    self.lstm4 = tf.keras.layers.LSTM(enc_units,
                           kernel_initializer=lstm_kernel_initializer,
                           recurrent_initializer=lstm_kernel_initializer,
                           return_sequences=True,
                           return_state=True,
                           dtype=dtype,
                           trainable=False)

  def lstm_encoder(self, x):
    output = self.lstm1(x)
    output = self.lstm2(output)
    output = self.lstm3(output)
    output, h_state, c_state = self.lstm4(output)

    return output, h_state, c_state

  def call(self, input_seq, hidden):
    x = self.embedding(input_seq)

    if args.profile == True:
        eval_time.append(["Encoder Embedding",
                            (timeit.timeit(lambda : self.embedding(input_seq), number = args.iterations)),
                            input_seq.shape, x.shape])
        print('encoder embed output dimensions(batch, timestep, units): {}'.format(x.shape))

    if args.functional_verify:
        orig_env = os.environ['ENABLE_PIM']

        os.environ['ENABLE_PIM'] = '0'
        output_gpu, h_state_gpu, c_state_gpu = self.lstm_encoder(x)

        os.environ['ENABLE_PIM'] = '1'
        output_pim, h_state_pim, c_state_pim = self.lstm_encoder(x)

        os.environ['ENABLE_PIM'] = orig_env

        result = np.testing.assert_array_almost_equal(output_pim, output_gpu, decimal=5)
        print("Functional Verification : {}".format(result))
        if os.environ['ENABLE_PIM']:
            output, h_state, c_state = output_pim, h_state_pim, c_state_pim
        else:
            output, h_state, c_state = output_gpu, h_state_gpu, c_state_gpu
    else:
        output, h_state, c_state = self.lstm_encoder(x)

    if args.profile == True:
        eval_time.append(["Encoder LSTM",
                            (timeit.timeit(lambda : self.lstm_encoder(x), number = args.iterations)),
                            x.shape, output.shape])

    return output, h_state, c_state

  def initialize_hidden_state(self):
    return tf.zeros((self.batch_sz, self.enc_units))

# Bahdanau Style Additive attention implementation
class BahdanauAttention(tf.keras.layers.Layer):
  def __init__(self, units):
    super(BahdanauAttention, self).__init__()
    self.W1 = tf.keras.layers.Dense(units)
    self.W2 = tf.keras.layers.Dense(units)
    self.V = tf.keras.layers.Dense(1)

  def call(self, query, values):
    # query hidden state shape == (batch_size, hidden size)
    # query_with_time_axis shape == (batch_size, 1, hidden size)
    # values shape == (batch_size, max_len, hidden size)
    # we are doing this to broadcast addition along the time axis to calculate the score
    query_with_time_axis = tf.expand_dims(query, 1)

    # score shape == (batch_size, max_length, 1)
    # we get 1 at the last axis because we are applying score to self.V
    # the shape of the tensor before applying self.V is (batch_size, max_length, units)
    score = self.V(tf.nn.tanh(
        self.W1(query_with_time_axis) + self.W2(values)))

    # attention_weights shape == (batch_size, max_length, 1)
    attention_weights = tf.nn.softmax(score, axis=1)

    # context_vector shape after sum == (batch_size, hidden_size)
    context_vector = attention_weights * values
    context_vector = tf.reduce_sum(context_vector, axis=1)

    return context_vector

# Decoder implementation for GNMT model
class Decoder(tf.keras.Model):
  def __init__(self, vocab_size, embedding_dim, dec_units, batch_sz, initializer, dtype):
    super(Decoder, self).__init__()
    self.batch_sz = batch_sz
    self.dec_units = dec_units
    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)
    self.lstm1 = tf.keras.layers.LSTM(dec_units,
                               kernel_initializer=initializer,
                               recurrent_initializer=initializer,
                               return_sequences=True,
                               dtype=dtype,
                               trainable=False)
    self.lstm2 = tf.keras.layers.LSTM(dec_units,
                               kernel_initializer=initializer,
                               recurrent_initializer=initializer,
                               return_sequences=True,
                               dtype=dtype,
                               trainable=False)
    self.lstm3 = tf.keras.layers.LSTM(dec_units,
                               kernel_initializer=initializer,
                               recurrent_initializer=initializer,
                               return_sequences=True,
                               dtype=dtype,
                               trainable=False)
    self.lstm4 = tf.keras.layers.LSTM(dec_units,
                               kernel_initializer=initializer,
                               recurrent_initializer=initializer,
                               return_sequences=True,
                               return_state=True,
                               dtype=dtype,
                               trainable=False)
    self.fc = tf.keras.layers.Dense(vocab_size)

    # used for attention
    self.attention = BahdanauAttention(self.dec_units)
    # self.attention = tf.keras.layers.AdditiveAttention(self.dec_units)

  def lstm_decoder(self, context_vector, x):
    # LSTM decoder layer 1
    #x = tf.concat([context_vector, x], axis=-1)
    x = tf.concat([tf.expand_dims(context_vector, 1), x], axis=-1)
    output = self.lstm1(x)

    # LSTM decoder layer 2
    #x = tf.concat([context_vector, x], axis=-1)
    x = tf.concat([tf.expand_dims(context_vector, 1), output], axis=-1)
    output = self.lstm2(x)

    # LST Mdecoder layer 3
    #x = tf.concat([context_vector, x], axis=-1)
    x = tf.concat([tf.expand_dims(context_vector, 1), output], axis=-1)
    output = self.lstm3(x)
    
    # LSTM decoder layer 4
    #x = tf.concat([context_vector, x], axis=-1)
    x = tf.concat([tf.expand_dims(context_vector, 1), output], axis=-1)
    return self.lstm4(x)

  def call(self, x, hidden, enc_output, dec_dict):
    # enc_output shape == (batch_size, max_length, hidden_size)
    #context_vector = self.attention([hidden, enc_output])
    context_vector = self.attention(hidden, enc_output)

    if args.profile == True:
        dec_dict["Attention"]["time"] += (timeit.timeit(lambda: self.attention(hidden, enc_output), number = args.iterations))
        dec_dict["Attention"]["Input"]  = hidden.shape, enc_output.shape
        dec_dict["Attention"]["Output"]  = context_vector.shape
    # print('Context vector dimensions: {}'.format(context_vector.shape))
    # print('Attention weights dimensions: {}'.format(attention_weights.shape))
    # x shape after passing through embedding == (batch_size, 1, embedding_dim)
    embed_x = self.embedding(x)
    
    if args.profile == True:
        dec_dict["Decoder Embedding"]["time"] += (timeit.timeit(lambda: self.embedding(x), number = args.iterations))
        dec_dict["Decoder Embedding"]["Input"] = x.shape
        dec_dict["Decoder Embedding"]["Output"] = embed_x.shape
    # print('Decoder embedding dimensions: {}'.format(x.shape))

    output , h_state, c_state = self.lstm_decoder(context_vector, embed_x)

    if args.profile == True:
        dec_dict["Decoder LSTM"]["time"] += (timeit.timeit(lambda: self.lstm_decoder(context_vector, embed_x), number = args.iterations))
        dec_dict["Decoder LSTM"]["Input"] = context_vector.shape, embed_x.shape
        dec_dict["Decoder LSTM"]["Output"] = output.shape

    # x shape after concatenation == (batch_size, 1, embedding_dim + hidden_size)
    # passing the concatenated vector to the LSTM
    # print('Decoder LSTM dimensions: (output),(hidden_state),(carry_state){}'.format(output.shape))
    # output shape == (batch_size * 1, hidden_size)
    reshaped_output = tf.reshape(output, (-1, output.shape[2]))

    if args.profile == True:
        dec_dict["Reshape"]["time"] += (timeit.timeit(lambda: tf.reshape(output, (-1, output.shape[2])), number=args.iterations))
        dec_dict["Reshape"]["Input"] = output.shape
        dec_dict["Reshape"]["Output"] = reshaped_output.shape

    # print('Reshape dimensions: {}'.format(output.shape))
    # output shape == (batch_size, vocab)

    x = self.fc(reshaped_output)

    if args.profile == True:
        dec_dict["Dense"]["time"] += (timeit.timeit(lambda: self.fc(output),number=args.iterations))
        dec_dict["Dense"]["Input"] = reshaped_output.shape
        dec_dict["Dense"]["Output"] = x.shape

    # print('Dense output dimensions: {}'.format(x.shape))

    return x, h_state

def create_gnmt_model(vocab_size, embed_dim, hidden, max_len, batch_size, initializer, dtype):
    encoder = Encoder(vocab_size, embed_dim, hidden, batch_size, initializer, dtype)
    decoder = Decoder(vocab_size, embed_dim, hidden, batch_size, initializer, dtype)

    return encoder, decoder

def initialize_data():
    input_seq   = tf.random.uniform(shape=(args.batch_size, args.max_seq_length), dtype=dtype)
    inputs = tf.convert_to_tensor(input_seq)
    dec_input  = tf.random.uniform(shape=(args.batch_size, 1), dtype=dtype)

    h_state = [tf.zeros((1, HIDDEN_SIZE))]
    c_state = [tf.zeros((1, HIDDEN_SIZE))]

    return inputs, dec_input, h_state, c_state

def evaluate(inputs, encoder, decoder, dtype, h_state, c_state, dec_input, max_length_targ):

    enc_out, enc_hidden, enc_carry = encoder(inputs, [h_state, c_state])

    if args.profile == True :
        print('Input dimensions: (batch_size, timestep){}'.format(inputs.shape))
        print('encoder output dimensions: {}'.format(enc_out.shape))
        print('encoder final hidden state dimensions: {}'.format(enc_hidden.shape))
        print('encoder final carry state dimensions: {}'.format(enc_carry.shape))

    dec_hidden = enc_hidden

    if args.profile == True:
        # for profiling of decoder
        dec_dict = {"Attention": { "time": 0, "Input": 0, "Output": 0},
                    "Decoder Embedding": {"time": 0, "Input": 0, "Output": 0},
                    "Decoder LSTM": {"time": 0, "Input": 0, "Output": 0},
                    "Reshape": {"time": 0, "Input": 0, "Output": 0},
                    "Dense": {"time": 0, "Input": 0, "Output": 0},
                    }
    else:
        dec_dict = {}

    for t in range(max_length_targ):
        predictions, dec_hidden = decoder(dec_input,
                                          dec_hidden,
                                          enc_out,
                                          dec_dict)

        predicted_id = tf.argmax(input=predictions, axis=1).numpy()

        # the predicted ID is fed back into the model
        dec_input = predicted_id.reshape((args.batch_size,1))

    if args.profile == True:
        for layer, data in dec_dict.items():
            eval_time.append([layer, data["time"], data["Input"], data["Output"]])

    return predictions

def gnmt_model_run(usr_args):
    global args 
    args = usr_args

    if args.dtype == 'fp32':
        global dtype
        dtype = tf.float32
    else:
        tf.keras.backend.set_floatx('float16')

    initializer = tf.keras.initializers.RandomNormal(seed=SEED)
    encoder, decoder = create_gnmt_model(VOCAB_SIZE, EMBEDDING_DIM, HIDDEN_SIZE, args.max_seq_length, args.batch_size, initializer, dtype)

    if args.profile:
        # model and gpu initialization and LUT load
        args.profile = False
        input_seq, dec_input, h_state, c_state = initialize_data()
        predictions = evaluate(input_seq, encoder, decoder, dtype, h_state, c_state, dec_input, args.max_seq_length)
        args.profile = True

    eval_time.clear()
    input_seq, dec_input, h_state, c_state = initialize_data()
    predictions = evaluate(input_seq, encoder, decoder, dtype, h_state, c_state, dec_input, args.max_seq_length)

    # Model Summary
    encoder.summary()
    decoder.summary()

    # Summation of all layers time
    evaltime_sum = sum(row[1] for row in eval_time)
    eval_time.append(["Sum of layers time", evaltime_sum, input_seq.shape, predictions.shape])

    if args.profile:
        # for disabling internal profiling calls.
        args.profile = False
        input_seq, dec_input, h_state, c_state = initialize_data()
        eval_time.append(["End to End", (timeit.timeit(lambda : evaluate(input_seq, encoder, decoder, dtype, h_state, c_state, dec_input, args.max_seq_length),
                            number = args.iterations)), input_seq.shape, predictions.shape])

        for i in range(len(eval_time)):
            eval_time[i][1] = (eval_time[i][1] * 1000 ) / args.iterations

        print(tabulate(eval_time, headers=["Index", "Layer", "Time(ms)", "Input", "Output"], showindex="always", tablefmt='github'))
        args.profile = True
