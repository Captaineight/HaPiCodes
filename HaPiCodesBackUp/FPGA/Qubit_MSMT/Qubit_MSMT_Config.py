from typing import List, Callable, Union, Tuple, Dict
from dataclasses import dataclass
import warnings
import pathlib

import numpy as np
from nptyping import NDArray
import yaml

import keysightSD1 as SD1
from  sd1_api.SD1AddOns import write_FPGA_memory, write_FPGA_register
import FPGA


fpga_path = pathlib.Path(FPGA.__path__[0])
CONFIG_DICT = yaml.safe_load(open(str(fpga_path)+r"\Qubit_MSMT\Qubit_MSMT_Markup.yaml", 'r'))

def check_register_constraint(reg_name: str, reg_val: int, constraint_dict: Dict, warning_message: str = None):
    lower_bound = constraint_dict[reg_name]["min"]
    upper_bound = constraint_dict[reg_name]["max"]
    min_eff = constraint_dict[reg_name].get("min_eff")  # minimum value to make the corresponding block functional
    if (reg_val < lower_bound) or (reg_val > upper_bound):
        raise ValueError(f"register {reg_name} does not satisfy the constraint [{lower_bound}, {upper_bound}]")
    if (min_eff is not None) and (reg_val < min_eff):
        warnings.warn(warning_message)

@dataclass
class FPGARegisters:
    """ a data class that stores the data that is going to be sent to FPGA.

    :param integ_trig_delay: in cycles,  integration start point counting from the FPGA trigger
    :param integ_length: in cycles, integration stop-integration start
    :param wf_trig_delay: in cycles,  weight function start point counting from the FPGA trigger
    :param wf_length: in cycles, length of weight function
    :param demod_trunc: lower bit offset for truncating the 35bit data after demodulation to 16 bit
    :param integ_trunc: lower bit offset for truncating the 32bit data after integration to 16 bit
    :param ref_sel: bit 0-1: ref channel, bit 2: ref_add. When 1,add the reference phase, else, subtract reference phase

    """
    demod_trunc: int
    integ_trig_delay: int
    integ_length: int
    integ_trunc: int
    wf_trig_delay: int # TODO: default=1 wf = constant 1
    wf_length: int
    ref_sel: int = 2 # ref_channel=2, ref_add = False

    def __post_init__(self):
        cstr_dict = CONFIG_DICT["register_constraints"]
        for k, v in self.__dict__.items():
            if k == "integ_trig_delay":
                min_eff_ = cstr_dict[k]["min_eff"]
                warn_msg = f"integration trigger delay is smaller than{min_eff_} , integration will not happen."
            elif k == "wf_trig_delay":
                min_eff_ = cstr_dict[k]["min_eff"]
                wf_idle_ = CONFIG_DICT["wf_idle_val"]
                warn_msg = f"weight function trigger delay is smaller than {min_eff_}, weight function will be constant {wf_idle_}."
            else:
                warn_msg = None
            check_register_constraint(k, v, cstr_dict, warn_msg)


def config_FPGA_registers(module_: SD1.SD_Module, channel:int, registers: FPGARegisters):
    for k, v in registers.__dict__.items():
        write_FPGA_register(module_, f"FPGARegisters_{channel}_{k}", v)


def configFPGA(module: SD1.SD_Module, channel:int,
               demod_trunc: int, integ_start: int, integ_stop: int, integ_trunc: int,
               ref_channel:int, ref_add: bool,
               wf_data: List[int] = None, wf_start: int = None, wf_stop:int = None):
    """

    :param module_: AIN module
    :param channel: channel to configure
    :param demod_trunc: lower bit offset for truncating the 35bit data after demodulation to 16 bit
    :param integ_start: in ns, integration start point
    :param integ_stop: in ns, integration stop point
    :param integ_trunc: lower bit offset for truncating the 32bit data after integration to 16 bit
    :param ref_channel: reference channel
    :param ref_add: When True, add the reference phase, otherwise, subtract reference phase
    :param wf_data: weight function data, 10 ns per point
    :param wf_start: in ns, weight function starting point
    :param wf_stop: in ns, weight function stop point
    :return:
    """
    if wf_data is None:
        wf_data = [32767]
        wf_start = 1 # no wait function
        wf_stop = 2
    else:
        if wf_start is None:
            wf_start = integ_start
        if wf_stop is None:
            wf_stop = integ_stop

    integ_length = integ_stop - integ_start
    wf_length = wf_stop - wf_start
    ref_sel_str = f"{int(ref_add)}" + f"{ref_channel - 1 :02b}"
    ref_sel_reg = int(ref_sel_str, base=2)
    FPGA_regs = FPGARegisters(demod_trunc, integ_start, integ_length, integ_trunc, wf_start, wf_length, ref_sel_reg)
    config_FPGA_registers(module, channel, FPGA_regs)

    write_FPGA_memory(module, f"WeightFunc_{channel}", wf_data)





