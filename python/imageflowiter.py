import numpy as np
import mxnet as mx
import os
import random
import cv2

class ImageFlowIter(mx.io.DataIter):
    def __init__(self, data_names, data_shapes, label_names, label_shapes, path_root, batch_size=3, frame_rate=30, shuffle=True):
        self._data_names = data_names
        self._data_shapes = data_shapes
        self._label_names = label_names
        self._label_shapes = label_shapes

        self._batch_size = batch_size
        self._path_root = path_root
        self._frame_rate = frame_rate
        self._shuffle = shuffle
        
        self._subdirs = [name for name in os.listdir(path_root) if os.path.isdir(os.path.join(path_root, name))]

        self.reset()

    def __iter__(self):
        return self

    def reset(self):
        if self._shuffle:
            random.shuffle(self._subdirs)

        self._cur_subdir_idx = 0
        self._cur_subdir_files = self._get_cur_subdir_files()
        self._subdir_batch_num = self._get_subdir_batch_num()
        self._cur_batch_idx = 0
        self._cur_batch_size = self._batch_size

    def __next__(self):
        return self.next()

    @property
    def provide_data(self):
        image_shape = self._data_shapes[0]
        flow_shape = self._data_shapes[1]
        batch_image_shape = (self._cur_batch_size,) + image_shape
        batch_flow_shape = (self._cur_batch_size, self._frame_rate) + flow_shape

        provide_data = zip(self._data_names, [batch_image_shape, batch_flow_shape])
        return provide_data

    @property
    def provide_label(self):
        batch_label_shape = (self._cur_batch_size,) + self._label_shapes[0]
        provide_label = zip(self._label_names, [batch_label_shape])
        return provide_label

    def next(self):
        if self._cur_subdir_idx < len(self._subdirs):
            if self._cur_batch_idx < self._subdir_batch_num:
                batch_start_idx = self._cur_batch_idx * self._batch_size
                batch_end_idx = self._get_batch_end_idx(batch_start_idx)
                self._cur_batch_size = batch_end_idx - batch_start_idx + 1

                data = self._read_batch_data(batch_start_idx, batch_end_idx)
                labels = self._read_batch_labels(batch_start_idx, batch_end_idx)
                print("images shape:" + str(data[0].shape))
                print("flows shape:" + str(data[1].shape))
                print("labels shape:" + str(labels[0].shape))
                
                self._cur_batch_idx += 1
                return mx.io.DataBatch(data, labels)
            else:
                self._cur_subdir_idx += 1
                if self._cur_subdir_idx < len(self._subdirs):
                    self._cur_subdir_files = self._get_cur_subdir_files()
                    self._subdir_batch_num = self._get_subdir_batch_num()
                    self._cur_batch_idx = 0

                    self.next()
        else:
            raise StopIteration

    def _get_cur_subdir_files(self):
        subdir_name = self._subdirs[self._cur_subdir_idx]
        files = []
        with open(self._path_root + "/" + subdir_name + '/' + 'files.txt', 'r') as f:
            for line in f:
                files.append(line.strip())

        return files

    def _get_subdir_batch_num(self):
        return len(self._cur_subdir_files) / self._batch_size + 1
    
    def _read_batch_data(self, batch_start_idx, batch_end_idx):
        batch_images = []
        batch_flows = []
        image_dir = self._path_root + "/" + self._subdirs[self._cur_subdir_idx] + '/' + 'images'
        flow_dir = self._path_root + "/" + self._subdirs[self._cur_subdir_idx] + '/' + 'flows'

        for i, file_name in enumerate(self._cur_subdir_files[batch_start_idx:batch_end_idx]):
            image_path = image_dir + '/' + file_name + '.png'
            print('image path:' + image_path)
            img = np.transpose(mx.image.imdecode(open(image_path).read()).asnumpy(), (2, 0, 1))
            batch_images.append(img)

            if i < (batch_end_idx-batch_start_idx):
                img_flows = self._get_img_flows(flow_dir, file_name)
                batch_flows.append(img_flows)
            else:
                batch_flows.append(np.zeros(img_flows.shape))

        return [mx.nd.array(batch_images), mx.nd.array(np.array(batch_flows))]

    def _read_batch_labels(self, batch_start_idx, batch_end_idx):
        labels = []
        label_dir = self._path_root + "/" + self._subdirs[self._cur_subdir_idx] + '/' + 'annot'
        for file_name in self._cur_subdir_files[batch_start_idx:batch_end_idx]:
            full_file_name = self._subdirs[self._cur_subdir_idx] + '_' + file_name.zfill(6) + '_L.png'
            label_path = label_dir + '/' + full_file_name
            print('label path:' + label_path)
            label = mx.image.imdecode(open(label_path).read(), flag=0).asnumpy()[:,:,0]
            labels.append(label)

        return [mx.nd.array(labels)]

    def _get_batch_end_idx(self, batch_start_idx):
        if (batch_start_idx + self._batch_size) < len(self._cur_subdir_files):
            return (batch_start_idx + self._batch_size)
        else:
            return len(self._cur_subdir_files)

    def _get_img_flows(self, flow_dir, image_file):
        flow_start_index = int(image_file)

        flows = []
        for i in range(self._frame_rate):
            flow_path = flow_dir + '/' + str(flow_start_index + i) + '_' + str(flow_start_index + i + 1) + '.flo'
            flow = self._read_flow(flow_path)
            flows.append(flow)

        img_flows = np.array(flows)
        return img_flows

    def _read_flow(self, file_name):
        f = open(file_name, 'rb')

        header = f.read(4)
        if header.decode("utf-8") != 'PIEH':
            raise Exception('Flow file header does not contain PIEH')

        width = np.fromfile(f, np.int32, 1).squeeze()
        height = np.fromfile(f, np.int32, 1).squeeze()

        flow = np.fromfile(f, np.float32, width * height * 2).reshape((height, width, 2))
        return flow.astype(np.float32)
