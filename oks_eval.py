import os
import numpy as np
import cv2
from scipy.spatial.distance import cdist
from tqdm import tqdm
from pathlib import Path
from ControlNet.annotator.openpose import OpenposeDetector
from ControlNet.annotator.util import resize_image, HWC3

# Initialize OpenPose detector
apply_openpose = OpenposeDetector()

# Function to calculate OKS
def calculate_oks(pred_keypoints, gt_keypoints, sigmas, bbox_area):
    """
    Calculate Object Keypoint Similarity (OKS).
    :param pred_keypoints: Predicted keypoints (numpy array, shape: [num_keypoints, 2])
    :param gt_keypoints: Ground truth keypoints (numpy array, shape: [num_keypoints, 2])
    :param sigmas: Standard deviations for keypoints (list or numpy array)
    :param bbox_area: Bounding box area of the object
    :return: OKS score
    """
    assert pred_keypoints.shape == gt_keypoints.shape, "Keypoints shape mismatch"
    
    # Compute squared distance between predicted and ground truth keypoints
    dists = np.sum((pred_keypoints - gt_keypoints) ** 2, axis=1)

    # Compute variance scaling factor
    variances = (2 * (sigmas ** 2)) * (bbox_area + np.finfo(float).eps)
    oks_scores = np.exp(-dists / variances)

    return np.mean(oks_scores)

# Function to extract pose from image using OpenPose
def extract_pose(image_path):
    """
    Extract keypoints from an image using OpenPose.
    :param image_path: Path to the image file
    :return: Extracted keypoints (numpy array, shape: [num_keypoints, 2])
    """
    image = cv2.imread(image_path)
    image = resize_image(HWC3(image), 512)  # Ensure image is properly resized for OpenPose
    detected_map, _ = apply_openpose(image)
    
    # Convert detected_map to keypoints (x, y)
    keypoints = []
    for point in detected_map:
        if point is not None:
            keypoints.append([point[0], point[1]])  # (x, y)
    return np.array(keypoints)

# Paths
ground_truth_folder = "poses"  # Folder containing ground truth poses (as PNGs)
generated_images_folder = "generated_images"  # Folder with images generated by knit.py

# Keypoint sigmas (COCO standard)
sigmas = np.array([0.26, 0.25, 0.25, 0.35, 0.35, 0.79, 0.79, 0.72, 0.72,
                   0.62, 0.62, 1.07, 1.07, 0.87, 0.87, 0.89, 0.89])

# Automate OKS calculation
oks_scores = []
for gt_file in tqdm(sorted(os.listdir(ground_truth_folder))):
    # Get corresponding generated image
    image_file = os.path.join(generated_images_folder, f"{Path(gt_file).stem}.png")
    if not os.path.exists(image_file):
        print(f"Generated image not found for {gt_file}")
        continue

    # Extract ground truth keypoints from the ground truth pose image
    gt_keypoints = extract_pose(os.path.join(ground_truth_folder, gt_file))

    # Extract predicted keypoints from generated image
    pred_keypoints = extract_pose(image_file)

    # Compute bounding box area (for OKS normalization)
    bbox_area = (np.max(gt_keypoints[:, 0]) - np.min(gt_keypoints[:, 0])) * \
                (np.max(gt_keypoints[:, 1]) - np.min(gt_keypoints[:, 1]))

    # Calculate OKS
    oks_score = calculate_oks(pred_keypoints, gt_keypoints, sigmas, bbox_area)
    oks_scores.append(oks_score)

    print(f"{gt_file}: OKS = {oks_score:.4f}")

# Summary statistics
print("\nEvaluation Summary:")
print(f"Average OKS Score: {np.mean(oks_scores):.4f}")
print(f"OKS Scores: {oks_scores}")
