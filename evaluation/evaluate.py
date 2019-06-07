import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.append('..')

from models import deeplab_resnet 
from collections import OrderedDict
from tools.utils import get_iou
from dataloader.datasets import DAVIS2016
import json
from evaluation.finetuning import finetune

davis_path = '/home/hakjine/datasets/DAVIS/DAVIS-2016/DAVIS'
im_path = os.path.join(davis_path, 'JPEGImages/480p')
gt_path = os.path.join(davis_path, 'Annotations/480p')

num_gpu = 0
os.environ['CUDA_VISIBLE_DEVICES'] = str(num_gpu)

def test_model(model, vis=False, save=True):
    model.eval()
    val_seqs = np.loadtxt(os.path.join(davis_path, 'val_seqs.txt'), dtype=str).tolist()
    dumps = OrderedDict()

    tiou = 0
    for seq in val_seqs:
        seq_path = os.path.join(im_path, seq)
        img_list = [os.path.join(seq, i)[:-4] for i in sorted(os.listdir(seq_path))]

        seq_iou = 0
        for idx, i in enumerate(img_list):

            img_original = cv2.imread(os.path.join(im_path,i+'.jpg'))
            img_original = cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB)
            img_temp = img_original.copy().astype(float)/255.
            oh, ow, oc = img_original.shape
            img_temp= cv2.resize(img_temp, (321, 321))
            h, w, c = img_temp.shape
            img_temp = img_temp.astype(float)

            gt_original = cv2.imread(os.path.join(gt_path,i+'.png'),0)
            gt_original[gt_original==255] = 1   
            gt = cv2.resize(gt_original, (w, h), interpolation=cv2.INTER_NEAREST)

            if idx == 0:
                fc = np.ones([h, w, 1], dtype=float) *-100/255.
                bb = cv2.boundingRect(gt.astype('uint8'))
                fc[bb[1]:bb[1]+bb[3], bb[0]:bb[0]+bb[2], 0] = 100/255.

            img = np.dstack([img_temp, fc])

            output = model(torch.FloatTensor(np.expand_dims(img, 0).transpose(0,3,1,2)).cuda())
            interp = nn.UpsamplingBilinear2d(size=(h, w))
            output = interp(output).data.cpu().numpy().squeeze()
            
            output = output.transpose(1,2,0)
            output = np.argmax(output,axis = 2)

            upsampled_output = cv2.resize(output.astype(np.float32), (ow, oh))
            upsampled_output[upsampled_output > 0.5] = 1
            upsampled_output[upsampled_output != 1] = 0

            iou = get_iou(upsampled_output, gt_original, 0)

            plt.ion()
            if vis:
                plt.subplot(2, 2, 1)
                plt.imshow(img_original)
                plt.subplot(2, 2, 2)
                plt.imshow(fc.squeeze())
                plt.subplot(2, 2, 3)
                plt.imshow(gt_original)
                plt.subplot(2, 2, 4)
                plt.imshow(upsampled_output)
                plt.show()
                plt.pause(0.01)
                plt.clf()

            fc = np.ones([h, w, 1], dtype=float) * -100/255.
            bb = cv2.boundingRect(output.astype('uint8'))
            if bb[2] != 0 and bb[3] != 0:
                fc[np.where(output==1)] = 100/255.

            if save:
                save_path = '../data/save/Result_masktrack'
                folder = os.path.join(save_path, i.split('/')[0])
                if not os.path.isdir(folder):
                    os.makedirs(folder)
                cv2.imwrite(os.path.join(save_path, i+'.png'),output*255)
            seq_iou += iou

        print(seq, seq_iou/len(img_list))
        dumps[seq] = seq_iou/len(img_list)
        tiou += seq_iou/len(img_list)

    dumps['t mIoU'] = tiou/len(val_seqs)
    with open('result.json', 'w') as f:
        json.dump(dumps, f, indent=2)

    model.train()
    return tiou/len(val_seqs)

if __name__ == '__main__':
    model = deeplab_resnet.Res_Deeplab_4chan(int(args['--NoLabels']))
    state_dict = torch.load('../data/snapshots/trained_masktrack_box.pth')
    model.load_state_dict(state_dict)
    model = model.cuda()
    model.eval()
    res = test_model(model, vis=args['--visualize'])
    print(res)
