
# coding: utf-8

# In[ ]:

import sys
sys.path.append('../')
import random
import numpy as np
import theano
import theano.tensor as T
from models import *
from data_import import *
from util import *
import layers
import optimizers
from experiment import *
from os.path import join
import argparse


# In[ ]:

# Turn on for debugging
DEBUG = False
if DEBUG:
    theano.config.optimizer='fast_compile'
    theano.config.exception_verbosity='high'


# In[ ]:

# variables that don't change between experiments/trials
constants = {
    'datadir': '../../data/',
    'glovedir':'../../data/glove',
    'report_wait': 500,
    'save_wait': 1000,
    'max_epochs': 50,
    'wv_dimensions': 50,  # speed up learning by using the smallest GloVe dimension
}


# In[ ]:

# step up argument parsing
parser = argparse.ArgumentParser()

parser.add_argument('-task_num', '--task_number', type=int, required=True)
parser.add_argument('-lr', '--base_lr', type=float, required=True)
parser.add_argument('-model', '--model_type', type=str, required=True)
parser.add_argument('-hd', '--hidden_dim', type=int, required=True)
parser.add_argument('-l2', '--l2_reg', type=float, required=True)

parser.add_argument('-lstm_hd', '--lstm_hidden_dim', type=int, required=True)
parser.add_argument('-mp', '--mean_pool', type=int, required=True)
parser.add_argument('-log', '--logging_path', type=str, required=True)


# In[ ]:

# variables that change between runs
if util.in_ipython():
    hyperparameters = {
        # data and logging
        'task_number': 1,  # {1, 3, 5, 17, 19}

        # HYPERPARAMETERS
        'base_lr': 1e-2,

        # all of the models
        'model_type': 'sentenceEmbedding',  # one of |sentenceEmbedding| or |averaging|
        'hidden_dim': 128,
        'l2_reg': 0.0,


        # specific to sentence embedding model
        'lstm_hidden_dim': 128,
        'mean_pool': False,
        
        'logging_path': 'logging_dir', 
    }
else:
    args = parser.parse_args()
    hyperparams = vars(args)


# In[ ]:

# load into namespace and log to metadata
for var, val in hyperparams.iteritems():
    exec("{0} = hyperparams['{0}']".format(var))
    util.metadata(var, val)
for var, val in constants.iteritems():
    exec("{0} = constants['{0}']".format(var))
    util.metadata(var, val)


# In[ ]:

# Load Data
train_ex, _ = get_data(datadir, task_number, test=False)
word_vectors = wordVectors(train_ex)
train_ex = examples_to_example_ind(word_vectors, train_ex)  # get examples in numerical format

# shuffle data
random.shuffle(train_ex)

# split the train into 90% train, 10% dev
train = train_ex[:int(.9 * len(train_ex))]
dev = train_ex[int(.9 * len(train_ex)):]


# In[ ]:

# get word_vectors (Using glove for now)
wv_matrix = word_vectors.get_wv_matrix(wv_dimensions, glovedir)


# In[ ]:

# set up the basic model
if model_type == 'averaging':
    model = averagingModel(wv_matrix, hidden_dim=hidden_dim, num_classes=wv_matrix.shape[1])
elif model_type == 'sentenceEmbedding':
    model = embeddingModel(wv_matrix, lstm_hidden_dim=lstm_hidden_dim, nn_hidden_dim=hidden_dim,
                            num_classes=wv_matrix.shape[1], mean_pool=mean_pool)


# In[ ]:

# generate answer probabilities and predictions
support_idxs = T.ivector()
question_idxs = T.ivector()

answer_probs = model.get_answer_probs(support_idxs, question_idxs)
answer_pred = T.argmax(answer_probs)


# In[ ]:

# define the loss and cost function
answer = T.ivector()
loss = -T.mean(T.log(answer_probs)[T.arange(answer.shape[0]), answer])
cost = loss + l2_reg * layers.l2_penalty(model.params)


# In[ ]:

# optimization
updates = optimizers.Adagrad(cost, model.params, base_lr=base_lr)


# In[ ]:

# compile functions to train and evaluate the model
print 'Compiling predict function'
model.predict = theano.function(
                   inputs = [support_idxs, question_idxs],
                   outputs = answer_pred)

print 'Compiling objective function'
model.objective = theano.function(
                    inputs = [support_idxs, question_idxs, answer],
                    outputs = loss)

print 'Compiling backprop function'
model.backprop = theano.function(
                    inputs=[support_idxs, question_idxs, answer],
                    outputs=[loss, answer_probs],
                    updates=updates)


# In[ ]:

# Set up the experiment object
controllers = [BasicController(report_wait=report_wait, save_wait=save_wait, max_epochs=max_epochs, path=logging_path)]

dset_samples =  len(dev)
observers = [ObjectiveObserver(dset_samples=dset_samples, report_wait=report_wait),
             AccuracyObserver(dset_samples=dset_samples, report_wait=report_wait)]

experiment = Experiment(model, train, dev, controllers=controllers, observers=observers, path=logging_path)


# In[ ]:

# launch the experiment
experiment.run_experiment()


# In[ ]:

## Plot learning curves
report(join(logging_path, 'history.cpkl'))

