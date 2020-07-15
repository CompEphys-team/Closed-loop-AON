#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/** 
 *  The script implements streaming image analysis part of the closed-loop system between MicroManager 
 *  and CaImAn toolbox (python). Two processes are communicating through named pipes, which are used for 
 *  sending signals that trigger specific processing steps in both environments. Images that are acquired 
 *  during the recording are saved in a multiTIFF file which is in turn read by CaImAn and used for online 
 *  analysis.
 *  
 *  author: Tea Tompos (master's internship project, June 2020)
 */

"""

# %% ********* Importing packages: *********
import caiman as cm
import logging
from pytictoc import TicToc
from caiman.source_extraction.cnmf import params as params
from caiman.source_extraction import cnmf as cnmf
import os, time
from caiman.paths import caiman_datadir

windows = os.name != 'posix'
if windows:
    import win32pipe, win32file, pywintypes

# %% ********* Creating named pipes for communication with MicroManager: *********
timer = TicToc()
timer.tic()    # start measuring time

sendPipeName = "getPipeMMCaImAn.ser"	       # FOR SENDING MESSAGES --> TO MicroManager
receivePipeName = "sendPipeMMCaImAn.ser"     # FOR READING MESSAGES --> FROM MicroManager

CaimanFileDirectory = caiman_datadir()   # specify where the file is saved

if windows:
    def p_create(name, read):
        return win32pipe.CreateNamedPipe(
            f'\\\\.\\pipe\\{name}',
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None)

    def p_open(pipe):
        for retry in range(4,-1,-1):
            try:
                win32pipe.ConnectNamedPipe(pipe, None)
                return pipe
            except pywintypes.error as e:
                print(f"Something went wrong, error {e.args[0]}, {retry} attempts remain")
                time.sleep(1)

    def p_close(pipe):
        win32file.CloseHandle(pipe)

    def p_write(pipe, message):
        win32file.WriteFile(pipe, message.encode('utf-8'))

    def p_read(pipe):
        res, buffer = win32file.ReadFile(pipe, 16384)
        return buffer.decode()
else:
    def p_create(name, read):
        path = f'/tmp/{name}'
        if os.path.exists(path):
            os.remove(path)
        os.mkfifo(path)
        if read:
            return open(path, 'r')
        else:
            return open(path, 'w', 1)

    def p_open(pipe):
        pass

    def p_close(pipe):
        name = pipe.name
        pipe.close()
        os.remove(name)

    def p_write(pipe, message):
        pipe.write(message + '\n')

    def p_read(pipe):
        return pipe.readline()[:-1]

pipeRead = p_create(receivePipeName, True)
pipeWrite = p_create(sendPipeName, False)

def cleanup():
    p_close(pipeWrite)
    p_close(pipeRead)

timer.toc()
# %% ********* Wait for file name: *********
print("Waiting for file name..")
p_open(pipeRead)
getFileName = p_read(pipeRead)

p_open(pipeWrite)

fullFileName = getFileName + '_MMStack_Default.ome.tif'
fileToProcess = os.path.join(CaimanFileDirectory, getFileName, fullFileName) # join downstream folders

print("File name received: " + fullFileName)
timer.toc()

# %% monkeypatch fit_next() so we can acces deltaf/f0 values during online analysis
def monkeypatch(func):
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        self = args[0] 
        process_frame(self)
        return result
    return wrapped

cnmf.online_cnmf.OnACID.fit_next = monkeypatch(cnmf.online_cnmf.OnACID.fit_next) # replace the class function

def process_frame(results):
    deltaf = results.estimates.C_on[0][-1] # last value in estimates.C_on should be deltaf/f0 for last processed frame
    print(deltaf) # this should be pushed to StdpC (instead of print), but values are not correct 
   
# %% ********* Defining parameters: *********
print("*** Defining analysis parameters ***")


fps = 40                # ideally it would be calculated by: (frame2-frame1) / totalTime(s)
decayTime = 0.45        # length of a typical transient in seconds
noiseStd = 'mean'       # PSD averaging method for computing noise std
arSystem = 1            # order of the autoregressive system 
expectedNeurons = 1     # number of expected neurons (upper bound), usually None, but we have only one in FOV
patches = None          # if None, the whole FOV is processed, otherwise: specify half-size of patch in pixels
onePhoton = True        # whether to use 1p processing mode
spatDown = 3            # spatial downsampling during initialisation, increase if there is memory problem (default=2)
tempDown = 1            # temporal downsampling during initialisation, increase if there is memory problem (default=2)
backDown = 5            # additional spatial downsampling factor for background (higher values increase the speed, without accuracy loss)
backComponents = 0      # number of background components (rank) if positive, else exact ring model with following settings
#                         gnb= 0: Return background as b and W
#                         gnb=-1: Return full rank background B
#                         gnb<-1: Don't return background
minCorr = 0.85          # minimum value of correlation image for determining a candidate component during greedy_pnr
minPNR = 20             # minimum value of psnr image for determining a candidate component during greedy_pnr
ringSize = 1.5          # radius of ring (*gSig) for computing background during greedy_pnr
minSNR = 1.5            # traces with SNR above this will get accepted
lowestSNR = 0.5         # traces with SNR below will be rejected
spaceThr = 0.9          # space correlation threshold, components with correlation higher than this will get accepted
neuronRadius = (120, 120) # radius of average neurons (in pixels)
neuronBound = (30, 30)  # half-size of bounding box for each neuron, in general 4*gSig+1


# params for OnACID:
spatDown_online = 3     # spatial downsampling factor for faster processing (if > 1)
epochs = 1              # number of times to go over data
expectedNeurons_online = 1  # number of expected components (for memory allocation purposes)
initFrames = 300        # length of mini batch used for initialization
initMethod_online = 'bare'  # or use 'cnmf'
minSNR_online = 1     # traces with SNR above this will get accepted
motCorrection = False   # flag for motion correction during online analysis
normalize_online = True     # whether to normalize each frame prior to online processing
cnnFlag = True              # whether to use the online CNN classifier for screening candidate components (otherwise space correlation is used)
thresh_CNN_noisy = 0.5      # threshold for the online CNN classifier

# create a dictionary with parameter-value pairs
initialParamsDict = { 'fnames': fileToProcess,
              'fr': fps,
              'decay_time': decayTime,
              'noise_method': noiseStd,
              'p': arSystem,
              'K': expectedNeurons,
              'rf': patches,
              'center_psf': onePhoton,
              'ssub': spatDown,
              'tsub': tempDown,
              'nb': backComponents,
              'min_corr': minCorr,
              'min_pnr': minPNR,
              'ring_size_factor': ringSize,
              'ssub_B': backDown,
              'normalize_init': False,                  # leave it True for 1p
              'update_background_components': False,    # improves results
              'method_deconvolution': 'oasis',          # could use 'cvxpy' alternatively
              'SNR_lowest': lowestSNR,
              'rval_thr': spaceThr,
              'gSig': neuronRadius,
              'gSiz': neuronBound,
           
        # params for OnACID:
              'ds_factor': spatDown_online,
              'epochs': epochs,
              'expected_comps': expectedNeurons_online,
              'init_batch': initFrames,
              'init_method':initMethod_online,  
              'min_SNR': minSNR_online,
              'motion_correct': motCorrection,
              'normalize': normalize_online,
              'save_online_movie': False,
              'show_movie': True,
              'update_num_comps': False,        # whether to search for new components
              'sniper_mode': cnnFlag,
              'thresh_CNN_noisy': thresh_CNN_noisy,

              
    }

# %% ********* Wait for pre-initialization trigger: *********
print("Now waiting for MicroManager to capture the first frame...")
triggerMessage_init = p_read(pipeRead)
print(triggerMessage_init)
expectedMessage_init = "FirstFrameReady"

#  ********* Start algorithm setup if the message is right: *********
if triggerMessage_init == expectedMessage_init:
    print("Setting up CaImAn...")
else:
    cleanup()
    raise RuntimeError("*** ERROR *** PRE-INITIALIZATION FAILED ***")

timer.toc()

# %% ********* Set up CaImAn: *********

allParams = params.CNMFParams(params_dict=initialParamsDict)    # define parameters in the params.CNMFParams
caimanResults = cnmf.online_cnmf.OnACID(params=allParams)       # pass parameters to caiman object


timer.toc()
# %% ********* Wait for initialization trigger message from MicroManager: *********
print("Now waiting for MicroManager to capture " + str(initFrames) + " initialization frames..")
triggerMessage_init = p_read(pipeRead)
print(triggerMessage_init)
expectedMessage_init = "startInitProcess"

#  ********* Start algorithm initialization if the message is right: *********
if triggerMessage_init == expectedMessage_init:
    print("*** Starting Initialization protocol with " + initMethod_online + " method ***")
    caimanResults.initialize_online()           # initialize model
else:
    cleanup()
    raise RuntimeError("*** ERROR *** INITIALIZATION FAILED ***")

timer.toc()
# %% ********* Visualize results of initialization: *********
print("Initialization finished. Choose threshold parameter to adjust accepted/rejected components!")
logging.info('Number of components:' + str(caimanResults.estimates.A.shape[-1]))
visual = cm.load(fileToProcess[0], subindices=slice(0,initFrames)).local_correlations(swap_dim=False)
caimanResults.estimates.plot_contours(img=visual)

#  ********* Use CNN clasifier to modify accepted/rejected components: *********
cnnThresh = 0.00001     # change threshold for CNN classifier to modify accepted/rejected components

# if true, pass through the CNN classifier with a low threshold (keeps clearer neuron shapes and excludes processes):
if cnnFlag:             
    allParams.set('quality', {'min_cnn_thr': cnnThresh})
    caimanResults.estimates.evaluate_components_CNN(allParams)
    caimanResults.estimates.plot_contours(img=visual, idx=caimanResults.estimates.idx_components)
    
# pause for user to decide on parameters
# input("Press Enter after the parameter is chosen...")
# %% ********* Send message to MicroManager to trigger data streaming: *********
triggerStream = "startStreamAcquisition"
p_write(pipeWrite, triggerStream)

print("CaImAn is ready for online analysis. Message was sent to MicroManager!")

timer.toc()
# %% ********* Wait for streaming analysis trigger message from MicroManager: *********
triggerMessage_analyse = p_read(pipeRead)
expectedMessage_analyse = "startStreamAnalysis"

#  ********* Start online analysis if the message is right: *********
if triggerMessage_analyse == expectedMessage_analyse:
    print("*** Starting online analysis with OnACID algorithm ***")
    caimanResults.fit_online()           # online analysis

timer.toc()
# %% Cleanup
cleanup()

# %% TO DO:
    #(1) get output from fit_online()  # tried with monkeypatch -> it works well but values are not
                                       # what I expected, i.e. OnACID does not allow access to frame-by-frame
                                       # data easily.. have to wait for toolbox update
    #(2) pass the values to stdpc






