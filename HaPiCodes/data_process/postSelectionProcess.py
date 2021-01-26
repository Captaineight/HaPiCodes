from typing import List, Callable, Union, Tuple, Dict
from typing_extensions import Literal
import warnings

import matplotlib.pyplot as plt
import h5py
import lmfit as lmf
import math
import yaml
import numpy as np
from matplotlib.widgets import Slider

from nptyping import NDArray
import h5py
import scipy as sp
from scipy.optimize import curve_fit
from matplotlib.patches import Circle, Wedge, Polygon
from scipy.ndimage import gaussian_filter as gf

from HaPiCodes.data_process import fittingAndDataProcess as fdp

class PostSelectionData():
    def __init__(self, data_I: NDArray, data_Q: NDArray, msmtInfoDict: dict, selPattern: List = [1, 0],
                 geLocation: List[float] = "AutoFit", plotGauFitting=True):
        """

        :param data_I:  I data
        :param data_Q:  Q data
        :param msmtInfoDict: dictionary from the measurement information yaml file
        :param selPattern: list of 1 and 0 that represents which pulse is selection and which pulse is experiment msmt
            in one experiment sequence. For example [1, 1, 0] represents, for each three data points, the first two are
            used for selection and the third one is experiment point.
        :param geLocation:  [g_x, g_y, e_x, e_y, g_r, e_r]
        """

        self.data_I = data_I
        self.data_Q = data_Q
        self.selPattern = selPattern
        self.msmtInfoDict = msmtInfoDict

        n_avg = len(data_I)
        pts_per_exp = len(data_I[0])
        msmt_per_sel = len(selPattern)
        if pts_per_exp % msmt_per_sel != 0:
            raise ValueError(f"selPattern is not valid. the length of selPattern {len(selPattern)} is no a factor of "
                             f"points per experiment {pts_per_exp}")
        self.sel_idxs = []
        self.exp_idxs = []
        for i in range(msmt_per_sel):
            if selPattern[i] not in [0, 1]:
                raise ValueError("values in slePattern must be 1(selection) or 0(experiment)")
            if selPattern[i] == 1:
                self.sel_idxs.append(np.arange(pts_per_exp)[i::msmt_per_sel])
            else:
                self.exp_idxs.append(np.arange(pts_per_exp)[i::msmt_per_sel])

        # gather selection data
        self.I_sel = np.array([data_I[:, s] for s in self.sel_idxs])
        self.Q_sel = np.array([data_Q[:, s] for s in self.sel_idxs])

        # gather experiment data
        self.I_exp = np.zeros((n_avg, pts_per_exp // msmt_per_sel, len(self.exp_idxs)))
        self.Q_exp = np.zeros((n_avg, pts_per_exp // msmt_per_sel, len(self.exp_idxs)))
        for i in range(n_avg):
            for j in range(pts_per_exp // msmt_per_sel):
                self.I_exp[i][j] = data_I[i, np.array(self.exp_idxs).T[j]]
                self.Q_exp[i][j] = data_Q[i, np.array(self.exp_idxs).T[j]]

        # fit for g, e gaussian if g/e state location is not provided
        if geLocation == "AutoFit":
            fitData = np.array([self.I_sel.flatten(), self.Q_sel.flatten()])
            fitRes = fdp.fit_Gaussian(fitData, plot=plotGauFitting, mute=1)
            sigma_g = np.sqrt(fitRes[4] ** 2 + fitRes[5] ** 2)
            sigma_e = np.sqrt(fitRes[6] ** 2 + fitRes[7] ** 2)
            geLocation = [*fitRes[:4], sigma_g, sigma_e]
        self.geLocation = geLocation
        self.g_x, self.g_y, self.e_x, self.e_y, self.g_r, self.e_r = self.geLocation

    def ge_split_line(self, x):
        center_x = (self.g_x + self.e_x) / 2
        center_y = (self.g_y + self.e_y) / 2
        k_ = -(self.g_x - self.e_x) / (self.g_y - self.e_y)
        return k_ * (x - center_x) + center_y

    def mask_g_by_circle(self, sel_idx: int, circle_size: float = 1, plot: bool = True):
        """
        :param sel_idx: index of the data for selection, must be '1' position in selPattern
        :param circle_size: size of the selection circle, in unit of g_r
        :param plot:
        :return:
        """
        if self.selPattern[sel_idx] != 1:
            raise ValueError(f"sel_idx must be a position with value 1 in selPattern {self.selPattern}")
        idx_ = np.where(np.where(np.array(self.selPattern) == 1)[0] == sel_idx)[0][0]
        I_sel_ = self.I_sel[idx_]
        Q_sel_ = self.Q_sel[idx_]
        print(idx_, I_sel_.shape)
        mask = (I_sel_ - self.g_x) ** 2 + (Q_sel_ - self.g_y) ** 2 < (self.g_r * circle_size) ** 2
        if plot:
            plt.figure(figsize=(7, 7))
            plt.title('g state selection range')
            plt.hist2d(I_sel_.flatten(), Q_sel_.flatten(), bins=101, range=self.msmtInfoDict['histRange'])
            theta = np.linspace(0, 2 * np.pi, 201)
            plt.plot(self.g_x + self.g_r * np.cos(theta), self.g_y + self.g_r * np.sin(theta), color='r')
        return mask

    def mask_g_by_line(self, sel_idx: int = 0, line_shift: float = 0, plot: bool = True):
        """
        :param sel_idx: index of the data for selection, must be '1' position in selPattern
        :param line_shift: shift the split line along the e -> g direction, in unit of half ge distance
        :param plot:
        :return:
        """
        if self.selPattern[sel_idx] != 1:
            raise ValueError(f"sel_idx must be a position with value 1 in selPattern {self.selPattern}")
        idx_ = np.where(np.where(np.array(self.selPattern) == 1)[0] == sel_idx)[0][0]
        I_sel_ = self.I_sel[idx_]
        Q_sel_ = self.Q_sel[idx_]

        shift_split_line = lambda x : self.ge_split_line(x - line_shift * 0.5 * (self.g_x - self.e_x)) \
                                      + line_shift * 0.5 * (self.g_y - self.e_y)
        if self.g_y < self.e_y:
            mask = Q_sel_ < shift_split_line(I_sel_)
        else:
            mask = Q_sel_ > shift_split_line(I_sel_)

        if plot:
            plt.figure(figsize=(7, 7))
            plt.title('g state selection range')
            h, xedges, yedges, image = plt.hist2d(I_sel_.flatten(), Q_sel_.flatten(), bins=101, range=self.msmtInfoDict['histRange'])
            plt.plot(xedges,shift_split_line(xedges),color='r')
        return mask


    def sel_data(self, mask, plot=True):
        self.I_vld = []
        self.Q_vld = []
        for i in range(self.I_exp.shape[1]):
            for j in range(self.I_exp.shape[2]):
                self.I_vld.append(self.I_exp[:, i, j][mask[:, i]])
                self.Q_vld.append(self.Q_exp[:, i, j][mask[:, i]])
        if plot:
            plt.figure(figsize=(7, 7))
            plt.title('experiment pts after selection')
            plt.hist2d(np.hstack(self.I_vld), np.hstack(self.Q_vld), bins=101, range=self.msmtInfoDict['histRange'])
        return self.I_vld, self.Q_vld

    def cal_g_pct(self):
        g_pct_list = []
        for i in range(len(self.I_vld)):
            I_v = self.I_vld[i]
            Q_v = self.Q_vld[i]
            n_pts = float(len(I_v))
            if self.g_y < self.e_y:
                mask = Q_v < self.ge_split_line(I_v)
            else:
                mask = Q_v < self.ge_split_line(I_v)
            g_pct_list.append(len(I_v[mask]) / n_pts)

        return np.array(g_pct_list)


if __name__ == "__main__":
    # directory = r'N:\Data\Tree_3Qubits\QCSWAP\Q3C3\20210111\\'
    directory = r''
    fileName = '10PiPulseTest'
    f = h5py.File(directory + fileName, 'r')
    Idata = np.real(f["rawData"])[:10000]
    Qdata = np.imag(f["rawData"])[:10000]
    msmtInfoDict = yaml.safe_load(open(directory + fileName + ".yaml", 'r'))
    # Idata = np.array([[2,2,4,5,6,  3,3,6,7,8], [4, 4, 8, 9,10,  5, 5, 10, 11,12]])
    # Qdata = -Idata


    IQsel = PostSelectionData(Idata, Qdata, msmtInfoDict, [1, 0])
    mask0 = IQsel.mask_g_by_line(0, line_shift=0, plot=True)
    mask0 = IQsel.mask_g_by_circle(0, circle_size=1, plot=True)
    I_vld, Q_vld = IQsel.sel_data(mask0, plot=True)
    I_avg, Q_avg = fdp.average_data(I_vld, Q_vld, axis0_type="xData")
    # I_rot, Q_rot = fdp.rotateData(I_avg, Q_avg, plot=0)
    g_pct = IQsel.cal_g_pct()

    xData = np.arange(10)
    plt.figure(figsize=(7, 7))
    plt.plot(xData, I_avg)
    plt.figure(figsize=(7, 7))
    plt.plot(xData, g_pct)