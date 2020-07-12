#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/** 
 *  The DEMO script implements streaming image analysis part of the closed-loop system between MicroManager 
 *  and CaImAn toolbox (python). Two processes are communicating through named pipes, which are used for 
 *  sending signals that trigger specific processing steps in both environments. Images that are acquired 
 *  during the recording are saved in a multiTIFF file which is in turn read by CaImAn and used for online 
 *  analysis.
 *  
 *  author: Tea Tompos (master's internship project, June 2020)
 */

"""

# %% ********* Importing packages: *********
import sys
import caiman as cm
import logging
from pytictoc import TicToc
from caiman.source_extraction.cnmf import params as params
from caiman.source_extraction import cnmf as cnmf
import os
from caiman.paths import caiman_datadir

# %% ********* Creating named pipes for communication with MicroManager: *********
timer = TicToc()
timer.tic()    # start measuring time

sendPipeName = "/tmp/getPipeMMCaImAn.ser"	       # FOR SENDING MESSAGES --> TO MicroManager
receivePipeName = "/tmp/sendPipeMMCaImAn.ser"     # FOR READING MESSAGES --> FROM MicroManager

MMfileDirectory = '/Applications/MicroManager 2.0 gamma/uMresults'
CaimanFileDirectory = caiman_datadir()   # specify where the file is saved 


if os.path.exists(sendPipeName):
   os.remove(sendPipeName)
   os.mkfifo(sendPipeName)
   print ("Removed old write-pipe, created new write-pipe.")
else: 
   os.mkfifo(sendPipeName)
   print ("Write-pipe created sucessfully!")
   
if os.path.exists(receivePipeName):
   os.remove(receivePipeName)
   os.mkfifo(receivePipeName)
   print ("Removed old read-pipe, created new read-pipe.")
else: 
   os.mkfifo(receivePipeName)
   print ("Read-pipe created sucessfully!")
    
timer.toc()
# %% ********* Wait for file name: *********
print("Waiting for file name..")
pipeRead = open(receivePipeName, 'r')                       # open the read pipe
getFileName = pipeRead.readline()[:-1]                      # wait for message

fullFileName = getFileName + '_MMStack_Default.ome.tif'
# fileToProcess = os.path.join(CaimanFileDirectory, 'example_movies', getFileName, fullFileName) # join downstream folders

print("File name received: " + fullFileName)
timer.toc()
# %% ********* Defining parameters: *********
print("*** Defining analysis parameters ***")
fileToProcess = os.path.join(CaimanFileDirectory, 'example_movies', 'demoCalciumRecording.tif') # FOR TESTING PURPOSES


fr = 40  # frame rate (Hz)
decay_time = .45  # approximate length of transient event in seconds (for GCaMP6s)
gSig = (26, 26)       # gaussian width of a 2D gaussian kernel, which approximates a neuron
gSiz = (120, 120)     # average diameter of a neuron, in general 4*gSig+1
p = 1  # order of AR indicator dynamics 
min_SNR = 0.2  # minimum SNR for accepting candidate components
thresh_CNN_noisy = 0.65  # CNN threshold for candidate components
gnb = 1  # number of background components
initMethod_online = 'bare'  # initialization method ('cnmf' will save init_file.hdf5, 'bare' will not.. not sure why)
deconv_method = 'oasis'

# set up CNMF initialization parameters
initFrames = 300  # number of frames for initialization
# patch_size = 400  # size of patch
# stride = 30  # amount of overlap between patches
K = 1  # max number of components in each patch
new_K = 0
cnnFlag = True

initialParamsDict = {'fr': fr,
               'fnames': fileToProcess,                # file used for initialization
               'decay_time': decay_time,
               'gSig': gSig,
               'gSiz': gSiz,
               'p': p,
               'center_psf': False,                 # set true for 1p data processing
               'simultaneously': True,             # whether to demix and deconvolve simultaneously
               'normalize': True,                  # whether to normalize each frame prior to online processing
               'min_SNR': min_SNR,
               'nb': gnb,
               'init_batch': initFrames,
               'init_method': initMethod_online,
               'rf': None,                          # half-size of patch in pixels. If None, no patches are constructed and the whole FOV is processed jointly
               #'stride': stride,
               'update_num_comps': False,
               'motion_correct': False,
               'sniper_mode': True,                 # whether to use the online CNN classifier for screening candidate components (otherwise space correlation is used)
               'thresh_CNN_noisy': thresh_CNN_noisy,
               'K': K,
               'expected_comps': K,
               'update_num_comps': False,           # whether to search for new components
               'min_num_trial': new_K,
               'method_deconvolution': deconv_method,
               'show_movie': True
               }


allParams = params.CNMFParams(params_dict=initialParamsDict)    # define parameters in the params.CNMFParams
caimanResults = cnmf.online_cnmf.OnACID(params=allParams)       # pass parameters to caiman object


timer.toc()
# %% ********* Wait for initialization trigger message from MicroManager: *********
print("Now waiting for MicroManager to capture " + str(initFrames) + " initialization frames..")

print("*** Starting Initialization protocol with " + initMethod_online + " method ***")
caimanResults.initialize_online()           # initialize model
    
    
timer.toc()
# %% ********* Visualize results of initialization: *********
print("Initialization finished. Choose threshold parameter to adjust accepted/rejected components!")
logging.info('Number of components:' + str(caimanResults.estimates.A.shape[-1]))
visual = cm.load(fileToProcess, subindices=slice(0,500)).local_correlations(swap_dim=False)
# caimanResults.estimates.plot_contours(img=visual)

#  ********* Use CNN clasifier to modify accepted/rejected components: *********
cnnThresh = 0.00001     # change threshold for CNN classifier to modify accepted/rejected components

# if true, pass through the CNN classifier with a low threshold (keeps clearer neuron shapes and excludes processes):
if cnnFlag:             
    allParams.set('quality', {'min_cnn_thr': cnnThresh})
    caimanResults.estimates.plot_contours(img=visual, idx=caimanResults.estimates.idx_components)
    caimanResults.estimates.evaluate_components_CNN(allParams)
    caimanResults.estimates.plot_contours(img=visual, idx=caimanResults.estimates.idx_components)
    

# %% ********* Send message to MicroManager to trigger data streaming: *********   

# input("Press Enter after the parameter is chosen...") # pause for user to decide on parameters

triggerStream = "startStreamAcquisition\n"      # include new line at the end
pipeWrite = open(sendPipeName, 'w', 1)          # write (1 is for activating line buffering)
pipeWrite.write(triggerStream)          # write to pipe

print("CaImAn is ready for online analysis. Message was sent to MicroManager!")

timer.toc()
# %% ********* Wait for streaming analysis trigger message from MicroManager: *********    
print("Waiting for MicroManager to start recording..")


#  ********* Start online analysis if the message is right: *********
if K==1: #triggerMessage_analyse == expectedMessage_analyse:
    print("*** Starting online analysis with OnACID algorithm ***")
    caimanResults.fit_online()           # online analysis
else:
    print("*** WARNING *** ONLINE ANALYSIS FAILED ***")
    #print("Wrong cue message. Received: " + triggerMessage_analyse + " of type: " + str(type(triggerMessage_analyse)) +
   #       "Expected: " + expectedMessage_analyse + " of type: " + str(type(expectedMessage_analyse)))
    while True:
        sys.exit()

        
# %% 
caimanResults.estimates.view_components(img=visual, idx=caimanResults.estimates.idx_components)
    
# %% TO DO:
    # get output from fit_online()
    # pass the values to stdpc

os.remove(sendPipeName)
os.remove(receivePipeName)





