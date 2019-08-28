import os
import sys
import json
import datetime
import numpy as np
import skimage.draw
import glob

# Root directory of the project
ROOT_DIR = os.path.abspath("../../")

# Import Mask RCNN
sys.path.append(ROOT_DIR)  # To find local version of the library
from mrcnn.config import Config
from mrcnn import model as modellib, utils

# Path to trained weights file
# COCO_WEIGHTS_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")
COCO_WEIGHTS_PATH = os.path.join(ROOT_DIR, "mask_rcnn_balloon.h5")

# Directory to save logs and model checkpoints, if not provided
# through the command line argument --logs
DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "logs")

###############################
## Configuration 
###############################

class EarConfig(Config):
    """Configuration for training on the AWE dataset.
    Derives from the base Config class and overrides some values.
    """
    # Give the configuration a recognizable name
    NAME = "ear"

    # We use a GPU with 12GB memory, which can fit two images.
    # Adjust down if you use a smaller GPU.
    IMAGES_PER_GPU = 1

    # Number of classes (including background)
    NUM_CLASSES = 1 + 1  # Background + ear

    # Number of training steps per epoch
    #STEPS_PER_EPOCH = 50

    # Backbone network architecture
    # Supported values are: resnet50, resnet101
    #BACKBONE = "resnet50"

###############################
## Dataset 
###############################

class EarDataset(utils.Dataset):

    def load_ear(self, dataset_dir, subset):
        """Load a subset of the AWE ear dataset.
        dataset_dir: Root directory of the dataset.
        subset: Subset to load: train or test    
        """
        
        # Add classes. We only have one class.
        self.add_class("ear", 1, "ear")
        
        # Assert folders train and test in dataset path
        assert subset in ["train", "test"]
        annotation = subset + 'annot'
        mask_dir = os.path.join(dataset_dir, annotation)
        dataset_dir = os.path.join(dataset_dir, subset)        
        
        images = []
        for (dirpath, dirnames, filenames) in os.walk(dataset_dir):    
            images.extend(filenames)       
            break
                
        for filename in images:
            image_path = os.path.join(dataset_dir, filename)
            mask_path = os.path.join(mask_dir, filename)
            img = skimage.io.imread(image_path)
            height, width = img.shape[:2]            
            self.add_image(
                "ear",
                image_id=os.path.splitext(filename)[0],
                path=image_path,
                width=width, 
                height=height,
                mask=mask_path #original mask
            )
        
    def load_mask(self, image_id):
        """Generate instance masks for an image.
        Returns:
        masks: A bool array of shape [height, width, instance count] with
            one mask per instance.
        class_ids: a 1D array of class IDs of the instance masks.
        """
        # If not a ear dataset image, delegate to parent class.
        image_info = self.image_info[image_id]
        if image_info["source"] != "ear":
            return super(self.__class__, self).load_mask(image_id)
        
        #mask = np.zeros([info["height"], info["width"], (#number_instances)], dtype=np.uint8)
        # Get a mask per instance        
        info = self.image_info[image_id]
        mask_root = os.path.splitext(info["mask"])[0]              
        parent = os.path.dirname(info["mask"])
        files = glob.glob(mask_root+'_?.*')        
        
        # Read mask files from .png image
        #return len(files), mask_root, parent
        mask = []        
        for i in range (0,len(files)):
            mask_path = os.path.join(parent, files[i])            
            m = skimage.io.imread(mask_path).astype(np.bool)
            mask.append(m)   
    
        mask = np.stack(mask, axis=-1)
        # Return mask, and array of class IDs of each instance. Since we have
        # one class ID only, we return an array of 1s
        return mask, np.ones([mask.shape[-1]], dtype=np.int32)

    def image_reference(self, image_id):
        """Return the path of the image."""
        info = self.image_info[image_id]
        if info["source"] == "ear":
            return info["path"]
        else:
            super(self.__class__, self).image_reference(image_id)

###############################
## Training
###############################

def train(model):
    """Train the model."""
    # Training dataset.
    dataset_train = EarDataset()
    dataset_train.load_ear(args.dataset, "train")
    dataset_train.prepare()

    # Validation dataset
    dataset_val = EarDataset()
    dataset_val.load_ear(args.dataset, "test")
    dataset_val.prepare()

    # *** This training schedule is an example. Update to your needs ***
    # Since we're using a very small dataset, and starting from
    # COCO trained weights, we don't need to train too long. Also,
    # no need to train all layers, just the heads should do it.
    print("Training network heads")
    model.train(dataset_train, dataset_val,
                learning_rate=config.LEARNING_RATE,
                epochs=30,
                layers='heads')

def color_splash(image, mask):
    """Apply color splash effect.
    image: RGB image [height, width, 3]
    mask: instance segmentation mask [height, width, instance count]

    Returns result image.
    """
    # Make a grayscale copy of the image. The grayscale copy still
    # has 3 RGB channels, though.
    gray = skimage.color.gray2rgb(skimage.color.rgb2gray(image)) * 255
    # Copy color pixels from the original color image where mask is set
    if mask.shape[-1] > 0:
        # We're treating all instances as one, so collapse the mask into one layer
        mask = (np.sum(mask, -1, keepdims=True) >= 1)
        splash = np.where(mask, image, gray).astype(np.uint8)
    else:
        splash = gray.astype(np.uint8)
    return splash

def detect(model, image_path=None, video_path=None):
    assert image_path or video_path

    # Image or video?
    if image_path:
        # Run model detection and generate the color splash effect
        print("Running on {}".format(args.image))
        # Read image
        image = skimage.io.imread(args.image)
        # Detect objects
        r = model.detect([image], verbose=1)[0]
        # Color splash
        splash = color_splash(image, r['masks'])
        # Save output
        file_name = "splash_{:%Y%m%dT%H%M%S}.png".format(datetime.datetime.now())
        skimage.io.imsave(file_name, splash)
    else:
        print("Video option not supported")
    print("Save to ", file_name)
############################################################
#  Training
############################################################

if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Train Mask R-CNN to detect ears.')
    parser.add_argument("command",
                        metavar="<command>",
                        help="'train' or 'evaluate'")
    parser.add_argument('--dataset', required=False,
                        metavar="/path/to/ear/dataset/",
                        help='Directory of the Ear Dataset')
    parser.add_argument('--weights', required=True,
                        metavar="/path/to/weights.h5",
                        help="Path to weights .h5 file or 'coco'")
    parser.add_argument('--logs', required=False,
                        default=DEFAULT_LOGS_DIR,
                        metavar="/path/to/logs/",
                        help='Logs and checkpoints directory (default=logs/)')
    parser.add_argument('--image', required=False,
                        metavar="path or URL to image",
                        help='Image to evaluate')
    parser.add_argument('--video', required=False,
                        metavar="path or URL to video",
                        help='Video to evaluate')
    args = parser.parse_args()

    # Validate arguments
    if args.command == "train":
        assert args.dataset, "Argument --dataset is required for training"
    elif args.command == "evaluate":
        assert args.image or args.video,\
               "Provide --image to evaluate"

    print("Weights: ", args.weights)
    print("Dataset: ", args.dataset)
    print("Logs: ", args.logs)

    # Configurations
    if args.command == "train":
        config = EarConfig()
    else:
        class InferenceConfig(EarConfig):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
        config = InferenceConfig()
    config.display()

    # Create model
    if args.command == "train":
        model = modellib.MaskRCNN(mode="training", config=config, model_dir=args.logs)
    else:
        model = modellib.MaskRCNN(mode="inference", config=config, model_dir=args.logs)

    # Select weights file to load
    if args.weights.lower() == "coco":
        weights_path = COCO_WEIGHTS_PATH
        # Download weights file
        if not os.path.exists(weights_path):
            utils.download_trained_weights(weights_path)
    elif args.weights.lower() == "last":
        # Find last trained weights
        weights_path = model.find_last()
    elif args.weights.lower() == "imagenet":
        # Start from ImageNet trained weights
        weights_path = model.get_imagenet_weights()
    else:
        weights_path = args.weights

    # Load weights
    print("Loading weights ", weights_path)
    if args.weights.lower() == "coco":
        # Exclude the last layers because they require a matching
        # number of classes
        model.load_weights(weights_path, by_name=True, exclude=[
            "mrcnn_class_logits", "mrcnn_bbox_fc", "mrcnn_bbox", "mrcnn_mask"])
    else:
        model.load_weights(weights_path, by_name=True)

    # Train or evaluate
    if args.command == "train":
        train(model)
    elif args.command == "evaluate":
        detect(model, image_path=args.image,video_path=args.video)
    else:
        print("'{}' is not recognized. "
              "Use 'train' or 'splash'".format(args.command))