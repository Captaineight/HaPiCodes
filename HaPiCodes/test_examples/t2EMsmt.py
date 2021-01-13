import yaml
import numpy as np
import matplotlib.pyplot as plt
import h5py
from HaPiCodes.pulse import basicMsmtPulses as amp
from HaPiCodes.data_process import fittingAndDataProcess as f
from HaPiCodes.pathwave.pxi_instruments import PXI_Instruments
from HaPiCodes.test_examples import msmtInfoSel


def t2EMsmt(yamlFile=msmtInfoSel.cwYaml, plot=1):
    msmtInfoDict = yaml.safe_load(open(yamlFile, 'r'))
    f.yamlFile = yamlFile
    pxi = PXI_Instruments(msmtInfoDict, reloadFPGA=True)
    WQ = amp.waveformAndQueue(pxi.module_dict, msmtInfoDict, subbuffer_used=pxi.subbuffer_used)
    W, Q = WQ.t2EMsmt()
    pxi.autoConfigAllDAQ(W, Q)
    pxi.uploadPulseAndQueue()
    dataReceive = pxi.runExperiment(timeout=20000)
    pxi.releaseHviAndCloseModule()
    Id, Qd = f.processDataReceive(pxi.subbuffer_used, dataReceive)
    t2E = f.t2_echo_fit(Id, Qd, plot=plot)
    return (W, Q, dataReceive, Id, Qd, t2E)


if __name__ == '__main__':
    msmt = t2EMsmt()
