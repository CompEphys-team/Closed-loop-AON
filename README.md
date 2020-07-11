# Closed-loop all-optical neurophys (AON)
Master's internship project. Repository contains scripts for establishing communication between software used in closed-loop all-optical neurophysiology (AON) experiment.

The AON experiment we are aiming to establish should work in a closed loop, for which we employ the power of 3 distinctive neuroscientific methods: fluorescence imaging, dynamic clamp and optogenetics. The most important components for all-optical closed-loop system are:
* fluorescent imaging of presynaptic neuron,
* activity-dependent modelling of synaptic response by dynamic clamp (DC), and
* DC-dependent photo-stimulation of postsynaptic neuron via LED/laser system. 

Experimental workflow starts by acquiring fluorescent signal from a single neuron we are imaging. This signal is processed by an image-processing algorithm which extracts single-neuron activity trace. Inferred neural activity serves as streaming input to dynamic clamp and, based on this data, DC models a response from user-defined artificial synapse. Simulated synaptic response in turn drives the behaviour of our photo-stimulation system (i.e. DC modulates the light properties used for stimulation of postsynaptic neuron). Protocol should be executed with minimal latency, i.e. with time-resolution as near to the real-time neural communication as possible.

Software list with details:

**MicroManager**: https://micro-manager.org


Used for hardware control. We couple our sCMOS Hamamatsu ORCA-Flash2.8 camera with MicroManager and perform fluorescence imaging. MicroManager has scripting option which gives user the power to further extend its capabilities. For purpose of closed-loop experiment, we have constructed a script for fast image acquisition and simultaneous communication between MicroManager and image analysis software (see CaImAn below).

**CaImAn**: https://caiman.readthedocs.io/en/master/Overview.html


Toolbox for processing recordings obtained with calcium or voltage imaging. One of its algorithms, namely OnACID, performs powerful online analysis of streaming fluorescence imaging data. This feature is implemented in our protocol as extension to the MicroManager imaging script. OnACID extracts fluorescence trace from a detected neuron in a streaming fashion by analysing data frame-by-frame, during the ongoing acquisition. Ideally, it would output inferred fluorescence values as they are being acquired, however, we are awaiting for such update from its developers.

**StdpC**: https://sourceforge.net/projects/stdpc/


Dynamic clamp software used for modelling of artificial synaptic response. We use StdpC in all-optical setup to modulate optogenetic signal used for photostimulation. StdpC should take streaming datapoints computed by OnACID (see CaImAn above) as its input, model the synaptic conductance and use simulated synaptic response to affect light intensity used for optogenetic photostimulation.
