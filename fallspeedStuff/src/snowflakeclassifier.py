# -*- coding: utf-8 -*-
"""SnowflakeClassifier

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1DbeA56PM-jxsuN6h7quThdJvm_5Gb4Qn

#Snowflake Detector
"""

#Bonus cell just for executing linux commands

!pip uninstall opencv-python-headless==4.5.5.62 
!pip install opencv-python-headless==4.1.2.30

"""#Setup"""

#Install dependecies
!pip install -q tflite-model-maker
!pip install -q tflite-support

#Needed imports although matplotlib, numpy,and pandas aren't currently used but will probably be needed
import tensorflow as tf

from tflite_model_maker.config import ExportFormat
from tflite_model_maker import model_spec
from tflite_model_maker import object_detector

import numpy as np
import pandas as pd
import matplotlib as plt

import os
import cv2

"""#Get the data and base model"""

#Picking what base model to use, efficientdet is just a starting place
#spec = model_spec.get('efficientdet_lite0')
#spec = model_spec.get('efficientdet_lite2')
spec = model_spec.get('efficientdet_lite4')

#Get dat data
#!curl -L "https://app.roboflow.com/ds/fosD79eC34?key=xH3OhXG8fK" > data.zip
#!unzip data.zip; rm data.zip
!curl -L "https://app.roboflow.com/ds/1XRSjPxvAk?key=B8s0tsnsPH" > roboflow.zip; unzip roboflow.zip; rm roboflow.zip

#I'm working on automating the jpeg and csv manipulation but right now I still hand format the csv

#!mkdir data
!mv ./test/*.jpg .
!mv ./train/*.jpg .
!mv ./valid/*.jpg .
#!mkdir annotations
#!mv ./test/*.csv ./annotations/test.csv
#!mv ./train/*.csv ./annotations/train.csv
#!mv ./valid/*.csv ./annotations/valid.csv
#!rm ./merged.csv
#!head -n 1 ./annotation/train.csv > merged.csv && tail -n+2 -q ./annotation/*.csv >> merged.csv

"""#Train and test"""

train_data, validation_data, test_data = object_detector.DataLoader.from_csv('./annotations.csv')

print(test_data.label_map)

#Output should be: {1: 'class', 2: 'Snowflake'}

# train_whole_model, controls layers being trained, setting to false uses transfer learning to train and
# only trains layers that don't match model_spec.config.var_freeze_expr.
model = object_detector.create(train_data, model_spec=spec, epochs = 5, batch_size=1, train_whole_model=True, validation_data=validation_data)

model.summary()
#There should be 15,108,198 parameters if using lite4

"""#Test"""

#Needs a bigger test set

#Prints mAP for whole model and specifically for each piece (class)
model.evaluate(test_data, batch_size=1)
#print (model.predict(test_data))

"""#Making and Testing the tflite version"""

# Defaults to post training full integer quantization when exported to tflite file
model.export(export_dir='.')

#Prints mAP for whole model and specifically for each piece (class)
model.evaluate_tflite('model.tflite', test_data)

from PIL import Image

model_path = 'model.tflite'

# Load the labels into a list
classes = ['???'] * model.model_spec.config.num_classes
label_map = model.model_spec.config.label_map
for label_id, label_name in label_map.as_dict().items():
  classes[label_id-1] = label_name

# Define a list of colors for visualization
COLORS = np.random.randint(0, 255, size=(len(classes), 3), dtype=np.uint8)

def preprocess_image(image_path, input_size):
  """Preprocess the input image to feed to the TFLite model"""
  img = tf.io.read_file(image_path)
  img = tf.io.decode_image(img, channels=3)
  img = tf.image.convert_image_dtype(img, tf.uint8)
  original_image = img
  resized_img = tf.image.resize(img, input_size)
  resized_img = resized_img[tf.newaxis, :]
  resized_img = tf.cast(resized_img, dtype=tf.uint8)
  return resized_img, original_image


def detect_objects(interpreter, image, threshold):
  """Returns a list of detection results, each a dictionary of object info."""

  signature_fn = interpreter.get_signature_runner()

  # Feed the input image to the model
  output = signature_fn(images=image)

  # Get all outputs from the model
  count = int(np.squeeze(output['output_0']))
  scores = np.squeeze(output['output_1'])
  classes = np.squeeze(output['output_2'])
  boxes = np.squeeze(output['output_3'])

  results = []
  for i in range(count):
    if scores[i] >= threshold:
      result = {
        'bounding_box': boxes[i],
        'class_id': classes[i],
        'score': scores[i]
      }
      results.append(result)
  return results


def run_odt_and_draw_results(image_path, interpreter, threshold=0.5):
  """Run object detection on the input image and draw the detection results"""
  # Load the input shape required by the model
  _, input_height, input_width, _ = interpreter.get_input_details()[0]['shape']

  # Load the input image and preprocess it
  preprocessed_image, original_image = preprocess_image(
      image_path,
      (input_height, input_width)
    )

  # Run object detection on the input image
  results = detect_objects(interpreter, preprocessed_image, threshold=threshold)

  # Plot the detection results on the input image
  original_image_np = original_image.numpy().astype(np.uint8)
  for obj in results:
    # Convert the object bounding box from relative coordinates to absolute
    # coordinates based on the original image resolution
    ymin, xmin, ymax, xmax = obj['bounding_box']
    xmin = int(xmin * original_image_np.shape[1])
    xmax = int(xmax * original_image_np.shape[1])
    ymin = int(ymin * original_image_np.shape[0])
    ymax = int(ymax * original_image_np.shape[0])

    # Find the class index of the current object
    class_id = int(obj['class_id'])

    # Draw the bounding box and label on the image
    color = [int(c) for c in COLORS[class_id]]
    cv2.rectangle(original_image_np, (xmin, ymin), (xmax, ymax), color, 2)
    # Make adjustments to make the label visible for all objects
    y = ymin - 15 if ymin - 15 > 15 else ymin + 15
    label = "{}: {:.0f}%".format(classes[class_id], obj['score'] * 100)
    cv2.putText(original_image_np, label, (xmin, y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

  # Return the final image
  original_uint8 = original_image_np.astype(np.uint8)
  return original_uint8

!rm ../image.png

INPUT_IMAGE_URL = "https://lh3.googleusercontent.com/80TAra6bhWnjfpprd9HHquVO5aCmvohGowH--cHZxiD1npvL4BlDj2n3pJvt84z9grG8I-nwED-yCuE6R8INPi-HfKv7Ua5NWCF2Xo7K1BkAfTk1Jpu1aAXyqS0-aXPF5TVwhjRG8KhYksP_VPaGecpAvZpBGKNns6SzfMRboX2SOMGWZBcFMrR0OXNe4wIYtaJvnz4biubq6b1omPZK0PCfoAVhLC05ATX6j4W0V_MthZ3FjJrdP5VJNKe94_ki4cUkcc4B4g1Oicd-yhWl0IaF3xbLKi13YPmtiitxYK0nCpDnH5BF3frzEX7r3dwG7zX3sdBPrPlSGB_Ki2gDYNOI6E8IPkQzhbakHD6QwNztsAfmQyP3LkpOE8dHf7FOqdvuFjrJy2vWCuIsr0lgUdgxcUqfUE0qG4iIUoJG1Pkyy9l54lfSikLbuSk6uKc1AzkUo0otZrwH9uzv_6isMCy1frynhHoP77iVsDXGUWXEHavntWkxlyzE81HxSe5xoai4suv6CwUZAL03vaJDaUuM45xw3kXk0pk_yewFLTtMuyPpJJd1aDpBT8eUHSWq72yruHt-jfPb5f5jGmihf3GetoYbq8mGdXpYvyN4buCZd8ztUDSw_y_fFSvmn7K8b0txIEaHbdZ-EhStABaYqndcBbyv9P6LP23j64WgV16J89lsyuTYLB0q_g4NQ7ph4JZNgzHhR6Y8qCxMmeNVUDCY=w1068-h893-no?authuser=0"
DETECTION_THRESHOLD = 0.2

TEMP_FILE = '/image.png'

!wget -q -O $TEMP_FILE $INPUT_IMAGE_URL
im = Image.open(TEMP_FILE)
im.thumbnail((2048, 1714), Image.ANTIALIAS)
im.save(TEMP_FILE, 'PNG')

# Load the TFLite model
interpreter = tf.lite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()

# Run inference and draw detection result on the local copy of the original file
detection_result_image = run_odt_and_draw_results(
    TEMP_FILE,
    interpreter,
    threshold=DETECTION_THRESHOLD
)

# Show the detection result
Image.fromarray(detection_result_image)

#Unused at the moment ****************************


# Load the TFLite model and allocate tensors.
interpreter = tf.lite.Interpreter(model_path="model.tflite")
interpreter.allocate_tensors()

# Get input and output tensors.
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Test the model on random input data.
input_shape = input_details[0]['shape']
input_data = np.array(np.random.random_sample(input_shape), dtype=np.float32)
interpreter.set_tensor(input_details[0]['index'], input_data)

interpreter.invoke()

# The function `get_tensor()` returns a copy of the tensor data.
# Use `tensor()` in order to get a pointer to the tensor.
output_data = interpreter.get_tensor(output_details[0]['index'])
print(output_data)

"""#Mount google drive for exports"""

#link drive for easy saving, although just downloading the model is easier
from google.colab import drive
drive.mount('/content/drive')

#Helper function for drawing a bounded box on an image
def draw_rect(image, box):
    y_min = int(max(1, (box[0] * image.height)))
    x_min = int(max(1, (box[1] * image.width)))
    y_max = int(min(image.height, (box[2] * image.height)))
    x_max = int(min(image.width, (box[3] * image.width)))
    
    # draw a rectangle on the image
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (255, 255, 255), 2)
