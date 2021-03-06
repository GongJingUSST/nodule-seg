'''Produce a segmentation of the lungs, and produce a set of seeds for that
segmentation.'''

from __future__ import print_function
import sys
import argparse
import SimpleITK as sitk  # pylint: disable=F0401
import os
import numpy as np


def otsu(img):
    '''Use an 'otsu' thresholding to segment out high- and low-attenuation
    regions. In every chest CT case I've seen, it produces an "air" region and
    a "soft tissue + bone" region, but a constrast CT might produce different
    results.'''

    array = sitk.GetArrayFromImage(img)
    minval = np.min(array)

    frac_minval = np.count_nonzero(array == minval) / float(array.size)

    filt = sitk.OtsuThresholdImageFilter()

    if frac_minval > .1:
        mask = np.logical_not(array == minval)
        mask = mask.astype('uint8')

        filt.SetMaskValue(1)
        filt.SetMaskOutput(False)

        mask = sitk.GetImageFromArray(mask)
        mask.CopyInformation(img)

        return filt.Execute(img, mask)
    else:
        return filt.Execute(img)


def dialate(img, probe_size):
    '''Once lungs are segmented out specifically, there's a tendency to get
    little islands in the lung fields. This dialatest the selection to remove
    islands and to generate a smoother segmentation.'''
    filt = sitk.BinaryDilateImageFilter()
    filt.SetKernelType(filt.Ball)
    filt.SetKernelRadius(probe_size)

    return filt.Execute(img, 0, 1, False)


def find_components(img):
    '''Produce a separate label for each region in the binary image. Takes the
    type at the edge of the image (specifically at 0,0,0) to be 1 and zero for
    all other labels.'''

    array = sitk.GetArrayFromImage(img)

    bg_fixed = array == array[0, 0, 0]
    bg_fixed = bg_fixed.astype(array.dtype)

    new_img = sitk.GetImageFromArray(bg_fixed)
    new_img.CopyInformation(img)

    filt = sitk.ConnectedComponentImageFilter()
    return filt.Execute(new_img)


def dump(img, name):
    '''Dump several slices for the given numpy array.'''
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigCanvas

    figure = Figure()
    canvas = FigCanvas(figure)

    nplot = 9
    for i in range(1, nplot+1):
        ax = figure.add_subplot(3, 3, i)  # pylint: disable=C0103
        ax.imshow(sitk.GetArrayFromImage(img)[i*img.GetDepth()/(nplot+1)])

    canvas.print_figure(name)


def isolate_lung_field(img):
    '''Isolate the lung field only by taking the largest object that is not
    the chest wall (identified as 0 due to Otsu filtering) or outside air
    (identified by appearing at the border).'''

    array = sitk.GetArrayFromImage(img)

    counts = np.bincount(np.ravel(array))

    outside = array[0, 0, 0]
    chest_wall = 0

    themax = (0, 0)
    for (obj_index, count) in enumerate(counts):
        if obj_index in [outside, chest_wall]:
            continue
        elif count > themax[1]:
            themax = (obj_index, count)

    lung_only = np.array(array == themax[0], dtype=array.dtype)
    lung_only = sitk.GetImageFromArray(lung_only)
    lung_only.CopyInformation(img)

    return lung_only


def isolate_not_biggest(img):
    '''Takes an sitk image with labels for many regions and produces a binary
    mask with zero for the largest region (by number of voxels) and one
    everywhere else.'''
    array = sitk.GetArrayFromImage(img)

    counts = np.bincount(np.ravel(array))

    big = np.argmax(counts)

    not_big = np.array(array != big, dtype=array.dtype)
    not_big = sitk.GetImageFromArray(not_big)
    not_big.CopyInformation(img)

    return not_big


def checkdist(seeds):
    '''UNDER CONSTRUCTION'''

    dists = {}

    for (i, seed) in enumerate(seeds):
        for oseed in seeds[i+1:]:
            dist = sum([(seed[k] - oseed[k])**2
                        for k in range(len(seed))])**0.5

            dists[(seed, oseed)] = dist

    raise NotImplementedError("Checkdist is under construction.")


def lungseg(img, options):
    '''Segment lung.'''
    img = otsu(img)
    img = find_components(img)
    img = isolate_lung_field(img)
    img = dialate(img, options['probe_size'])
    img = find_components(img)
    img = isolate_not_biggest(img)
    img = sitk.BinaryErode(img, options['probe_size']/2,
                           sitk.BinaryErodeImageFilter.Ball)

    return img
