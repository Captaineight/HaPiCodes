import yaml
import numpy as np
import matplotlib.pyplot as plt
import h5py
from HaPiCodes.pulse import basicMsmtPulses as amp
from HaPiCodes.data_process import fittingAndDataProcess as f
from HaPiCodes.pathwave.pxi_instruments import PXI_Instruments
from HaPiCodes.test_examples import msmtInfoSel

msmtInfoDict = yaml.safe_load(open(msmtInfoSel.cwYaml, 'r'))
f.yamlFile = msmtInfoSel.cwYaml


def piPulseTuneUp(plot=1, update=0):
    pxi = PXI_Instruments(msmtInfoDict, reloadFPGA=True)
    WQ = amp.waveformAndQueue(pxi.module_dict, msmtInfoDict, subbuffer_used=pxi.subbuffer_used)
    W, Q = WQ.piPulseTuneUp()
    pxi.autoConfigAllDAQ(W, Q)
    pxi.uploadPulseAndQueue()
    dataReceive = pxi.runExperiment(timeout=20000)
    pxi.releaseHviAndCloseModule()
    Id, Qd = f.processDataReceive(pxi.subbuffer_used, dataReceive)

    # IQdata = f.processDataReceiveWithRef(pxi.subbuffer_used, dataReceive, plot=1)
    # Id, Qd = f.average_data(IQdata.I_rot, IQdata.Q_rot)
    piPulseAmp = f.pi_pulse_tune_up(Id, Qd, updatePiPusle_amp=update, plot=plot)
    return (W, Q, dataReceive, Id, Qd, piPulseAmp)

if __name__ == '__main__':
    msmt = piPulseTuneUp()