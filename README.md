# Closed-loop all-optical neurophys (AON)
Master's internship project. 
Repository contains scripts for establishing communication between software used in closed-loop all-optical neurophysiology (AON) experiment. See Wiki for more details.

**Directory tree:**

 _./demos_
  
 This folder contains demo acquisition script (for MicroManager software), demo analysis script (for CaImAn/python toolbox) and a calcium recording movie for testing the two scripts. See Wiki for more details. Scripts demonstrate continuous image acquisition and simultaneous analysis of streaming frames.
 
 
 _./scripts_

This folder contains original image acquisition and image analysis scripts. They should be tested during actual imaging conditions. Different to demo files, analysis script provided here extracts (and displays) frame-by-frame fluorescence values calculated by CaImAn. Captured values should serve as streaming input to StdpC, however, they do not seem to be correct. Further research needs to be done to evaluate CaImAn algorithm for proper data output to StdpC.
