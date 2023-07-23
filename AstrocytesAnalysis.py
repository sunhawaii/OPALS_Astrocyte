import sys
import os
import math
import numpy as np
import numpy.ma as ma
from cellpose import models, utils
from matplotlib import pyplot as plt
import multiprocessing
import time
import json
from natsort import natsorted
from tqdm import tqdm

#start timer to measure how long code takes to execute
start_time=time.time()

def load_path(file):
    f = open(file)
    path = f.readline().rstrip()
    f.close()
    return path

def get_center_location(o):
    #takes average
    return o[:, 0].mean(), o[:, 1].mean()

def generate_masks():
    i = 0
    for o in nucOutlines:
        # nuclei
        # get average x and y
        centerX, centerY = get_center_location(o)
        plt.annotate(str(i), (centerX, centerY), color="white")

        plt.plot(o[:,0], o[:,1], color='r')

        #get standard deviation
        stdX = np.std(o[:,0])
        stdY = np.std(o[:,1])
        stdMax = max(stdX, stdY)

        # cytoplasm
        # see if there is a cytoplasm that is close enough to a nucleus to use
        hasCloseCytoplasm = False
        closeMaskId = 1
        for c in cytoOutlines: 
            cytoCenterX, cytoCenterY = get_center_location(c)
            if math.dist([centerX, centerY], [cytoCenterX, cytoCenterY]) < 50:
                hasCloseCytoplasm = True
                break
            closeMaskId+=1

        # use only the relavant part of the cytoplasm mask 
        mask = cytoWholeMask == closeMaskId
        # use original circle method if there are no valid cytoplasm masks
        if not hasCloseCytoplasm:
            plt.plot(centerX, centerY, marker=".", markerfacecolor=(0, 0, 0, 0), markeredgecolor=(0, 0, 1, 1), markersize=2*stdMax)
            h, w = samplingImage.shape[:2]
            mask = create_circular_mask(h, w, center=(centerX, centerY), radius=2*stdMax)
        
        # remove the nucleus from the mask
        mask[nucWholeMask] = 0
        masks.append(mask)
        i+=1

def save_masks(masks):
    combined_mask = np.empty(())
    for mask in masks:
        combined_mask = np.dstack(combined_mask, mask)
    np.save("masks.npy",combined_mask)

def sample_data(graphData, first_image_sample, first_image_normalized_intensities):
    temp = []
    min_intensity = np.min(samplingImage)
    for mask in masks:
        intensity = np.sum(samplingImage[mask]) / np.sum(mask)
        normalized_intensity = (intensity - min_intensity)
        temp.append(normalized_intensity)
        if first_image_sample:
            first_image_normalized_intensities.append(normalized_intensity)
    
    first_image_sample = False
    temp = [i / j for i, j in zip(temp, first_image_normalized_intensities)]

    graphData = np.column_stack((graphData, temp))
    return graphData, first_image_sample, first_image_normalized_intensities

def display_data(graphData):
    graphData = np.delete(graphData, 0, 1)

    fullMask = np.zeros(nucWholeMask.shape)
    for mask in masks:
        fullMask = np.add(fullMask, mask)
    fullMask = fullMask > 0

    # for displaying the main image (subplot must be commented)
    samplingImage[~fullMask] = 0
    plt.imshow(samplingImage)

    plt.savefig("masks", format="png")

    split_point = len(pre_image_paths)

    post_offset = []
    for i in range(len(pre_image_paths), len(pre_image_paths) + len(post_image_paths)):
        post_offset.append(i)

    for i in range(len(masks)):
        plt.clf()
        # pre graph
        plt.plot(graphData[i][:split_point], color="blue")
        # connecting line
        x_points = np.array([split_point-1, split_point])
        y_points = np.array([graphData[i][split_point-1], graphData[i][split_point]])
        plt.plot(x_points, y_points, color="red")
        # post graph
        plt.plot(post_offset, graphData[i][split_point:], color="red")
        plt.savefig("plot" + str(i), format="png")

    
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"The function took {execution_time} seconds to run.")

def create_circular_mask(h, w, center=None, radius=None):
    if center is None: # use the middle of the image
        center = (int(w/2), int(h/2))
    if radius is None: # use the smallest distance between the center and image walls
        radius = min(center[0], center[1], w-center[0], h-center[1])

    Y, X = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y-center[1])**2)

    mask = dist_from_center <= radius
    return mask

if __name__ == '__main__':
    multiprocessing.freeze_support()

    # Load the configuration file
    config = []
    with open("config.json") as f:
        config = json.load(f)

    # for quick running a single image
    #nucDat = np.load(load_path("nucleiMaskLocation.txt"), allow_pickle=True).item()
    #cytoDat = np.load(load_path("cytoMaskLocation.txt"), allow_pickle=True).item()

    pre_dir_path = config["pre_directory_location"]
    post_dir_path = config["post_directory_location"]

    pre_image_paths = os.listdir(pre_dir_path)
    pre_image_paths = natsorted(pre_image_paths)

    post_image_paths = os.listdir(post_dir_path)
    post_image_paths = natsorted(post_image_paths)

    samplingImage = plt.imread(os.path.join(pre_dir_path, pre_image_paths[0]))
    first_image_sample = True
    first_image_normalized_intensities = []

    # for quick running a single image
    #samplingImage = plt.imread(load_path("imgLocation.txt"))

    nucModel = models.CellposeModel(gpu=True, pretrained_model=str(config["nuclei_model_location"]))
    cytoModel = models.CellposeModel(gpu=True, pretrained_model=str(config["cyto_model_location"]))

    nucDat = nucModel.eval(samplingImage, channels=[2,0])[0]
    cytoDat = cytoModel.eval(samplingImage, channels=[2,0])[0]

    # plot image with outlines overlaid in red
    #nucOutlines = utils.outlines_list(nucDat['masks'])
    nucOutlines = utils.outlines_list(nucDat)
    #cytoOutlines = utils.outlines_list(cytoDat['masks'])
    cytoOutlines = utils.outlines_list(cytoDat)

    masks = []

    #masks = np.load("masks.npy")

    # for quick running a single image
    #nucWholeMask = nucDat['masks']
    nucWholeMask = nucDat
    nucWholeMask = nucWholeMask > 0

    # for quick running a single image
    #cytoWholeMask = cytoDat['masks']
    cytoWholeMask = cytoDat

    generate_masks()
    #save_masks(masks)

    graphData = np.zeros(len(masks))

    graphData, first_image_sample, first_image_normalized_intensities = sample_data(graphData, first_image_sample, first_image_normalized_intensities)

    i = 0
    for image_path in tqdm(pre_image_paths):
        if i > 0:
            samplingImage = plt.imread(os.path.join(pre_dir_path, pre_image_paths[i]))
            graphData, first_image_sample, first_image_normalized_intensities = sample_data(graphData, first_image_sample, first_image_normalized_intensities)
        i+=1

    i = 0
    for image_path in tqdm(post_image_paths):
        samplingImage = plt.imread(os.path.join(post_dir_path, post_image_paths[i]))
        graphData, first_image_sample, first_image_normalized_intensities = sample_data(graphData, first_image_sample, first_image_normalized_intensities)
        i+=1

    # stitch together all of the masks
    display_data(graphData)
