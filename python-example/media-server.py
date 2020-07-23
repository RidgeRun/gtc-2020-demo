#!/usr/bin/env python3

import time
from pygstc.gstc import *

# Create PipelineEntity object to manage each pipeline
class PipelineEntity(object):
    def __init__(self, client, name, description):
        self._name = name
        self._description = description
        self._client = client
        print("Creating pipeline: " + self._name)
        self._client.pipeline_create(self._name, self._description)
    def play(self):
        print("Playing pipeline: " + self._name)
        self._client.pipeline_play(self._name)
    def stop(self):
        print("Stopping pipeline: " + self._name)
        self._client.pipeline_stop(self._name)
    def delete(self):
        print("Deleting pipeline: " + self._name)
        self._client.pipeline_delete(self._name)
    def eos(self):
        print("Sending EOS to pipeline: " + self._name)
        self._client.event_eos(self._name)
    def set_file_location(self, location):
        print("Setting " + self._name + " pipeline recording/snapshot location to " + location);
        filesink_name = "filesink_" + self._name;
        self._client.element_set(self._name, filesink_name, 'location', location);
    def listen_to(self, sink):
        print(self._name + " pipeline listening to " + sink);
        self._client.element_set(self._name, self._name + '_src', 'listen-to', sink);

pipelines_base = []
pipelines_video_rec = []
pipelines_video_enc = []
pipelines_snap = []

# Create GstD Python client
client = GstdClient()

# Create camera pipelines
camera0 = PipelineEntity(client, 'camera0', 'v4l2src device=/dev/video1 ! video/x-raw,format=YUY2,width=1280,height=720 ! interpipesink name=camera0 forward-events=true forward-eos=true sync=false')
pipelines_base.append(camera0)

camera0_rgba_nvmm = PipelineEntity(client, 'camera0_rgba_nvmm', 'interpipesrc listen-to=camera0 ! video/x-raw,format=YUY2,width=1280,height=720 ! videoconvert ! video/x-raw,format=NV12,width=1280,height=720 ! nvvideoconvert ! video/x-raw(memory:NVMM),format=RGBA,width=1280,height=720 ! queue ! interpipesink name=camera0_rgba_nvmm forward-events=true forward-eos=true sync=false caps=video/x-raw(memory:NVMM),format=RGBA,width=1280,height=720,pixel-aspect-ratio=1/1,interlace-mode=progressive,framerate=30/1')
pipelines_base.append(camera0_rgba_nvmm)

camera1 = PipelineEntity(client, 'camera1', 'nvarguscamerasrc ! nvvidconv ! video/x-raw,format=I420,width=1280,height=720 ! queue ! interpipesink name=camera1 forward-events=true forward-eos=true sync=false')
pipelines_base.append(camera1)

camera1_rgba_nvmm = PipelineEntity(client, 'camera1_rgba_nvmm', 'interpipesrc listen-to=camera1 ! video/x-raw,format=I420,width=1280,height=720 ! nvvideoconvert ! video/x-raw(memory:NVMM),format=RGBA,width=1280,height=720 ! interpipesink name=camera1_rgba_nvmm forward-events=true forward-eos=true sync=false caps=video/x-raw(memory:NVMM),format=RGBA,width=1280,height=720,pixel-aspect-ratio=1/1,interlace-mode=progressive,framerate=30/1')
pipelines_base.append(camera1_rgba_nvmm)

# Create Deepstream pipeline with 4 cameras processing
deepstream = PipelineEntity(client, 'deepstream', 'interpipesrc listen-to=camera0_rgba_nvmm ! nvstreammux0.sink_0 interpipesrc listen-to=camera0_rgba_nvmm ! nvstreammux0.sink_1 interpipesrc listen-to=camera1_rgba_nvmm ! nvstreammux0.sink_2 interpipesrc listen-to=camera1_rgba_nvmm ! nvstreammux0.sink_3 nvstreammux name=nvstreammux0 batch-size=4 batched-push-timeout=40000 width=1280 height=720 ! queue ! nvinfer batch-size=4 config-file-path=../deepstream-models/config_infer_primary_4_cameras.txt ! queue ! nvtracker ll-lib-file=../deepstream-models/libnvds_mot_klt.so enable-batch-process=true ! queue ! nvmultistreamtiler width=1280 height=720 rows=2 columns=2 ! nvvideoconvert ! nvdsosd ! queue ! interpipesink name=deep forward-events=true forward-eos=true sync=false')
pipelines_base.append(deepstream)

# Create encoding pipelines
h264 = PipelineEntity(client, 'h264', 'interpipesrc name=h264_src format=time listen-to=deep ! video/x-raw(memory:NVMM),format=RGBA,width=1280,height=720 ! nvvideoconvert ! nvv4l2h264enc ! interpipesink name=h264_sink forward-events=true forward-eos=true sync=false async=false enable-last-sample=false drop=true')
pipelines_video_enc.append(h264)

h265 = PipelineEntity(client, 'h265', 'interpipesrc name=h265_src format=time listen-to=deep ! nvvideoconvert ! nvv4l2h265enc ! interpipesink name=h265_sink forward-events=true forward-eos=true sync=false async=false enable-last-sample=false drop=true')
pipelines_video_enc.append(h265)

jpeg = PipelineEntity(client, 'jpeg', 'interpipesrc name=jpeg_src format=time listen-to=deep ! nvvideoconvert ! video/x-raw,format=I420,width=1280,height=720 ! nvjpegenc ! interpipesink name=jpeg forward-events=true forward-eos=true sync=false async=false enable-last-sample=false drop=true')
pipelines_snap.append(jpeg)

# Create recording pipelines
record_h264 = PipelineEntity(client, 'record_h264', 'interpipesrc format=time allow-renegotiation=false listen-to=h264_sink ! h264parse ! matroskamux ! filesink name=filesink_record_h264 location=test-h264.mkv')
pipelines_video_rec.append(record_h264)

record_h265 = PipelineEntity(client, 'record_h265', 'interpipesrc format=time listen-to=h265_sink ! h265parse ! matroskamux ! filesink name=filesink_record_h265 location=test-h265.mkv')
pipelines_video_rec.append(record_h265)

# Create snapshot pipeline
snapshot = PipelineEntity(client, 'snapshot', 'interpipesrc format=time listen-to=jpeg num-buffers=1 ! filesink name=filesink_snapshot location=test-snapshot.jpg')
pipelines_snap.append(snapshot)

# Create display pipeline
display = PipelineEntity(client, 'display', 'interpipesrc listen-to=deep ! nvegltransform bufapi-version=true ! nveglglessink qos=false async=false sync=false')
pipelines_base.append(display)

# Play base pipelines
for pipeline in pipelines_base:
    pipeline.play()

time.sleep(10)

# Set locations for video recordings
for pipeline in pipelines_video_rec:
    pipeline.set_file_location('test_' + pipeline._name + '_0.mkv')

# Play video recording pipelines
for pipeline in pipelines_video_rec:
    pipeline.play()

# Play video encoding pipelines
for pipeline in pipelines_video_enc:
    pipeline.play()

time.sleep(20)

# Set location for snapshot
snapshot.set_file_location('test_' + snapshot._name + '_0.jpeg')

# Play snapshot pipelines
for pipeline in pipelines_snap:
    pipeline.play()

time.sleep(5)

# Take another snapshot, but now use camera0 as source
snapshot.stop()
jpeg.listen_to('camera0_rgba_nvmm')
snapshot.set_file_location('test_' + snapshot._name + '_1.jpg')
snapshot.play()

# Stop previous recordings, connect to camera 1 capture instead of deepstream output and record another video
# Send EOS event to encode pipelines for proper closing
# EOS to recording pipelines
for pipeline in pipelines_video_enc:
    pipeline.eos()

# Stop recordings
for pipeline in pipelines_video_rec:
    pipeline.stop()
for pipeline in pipelines_video_enc:
    pipeline.stop()

for pipeline in pipelines_video_enc:
    pipeline.listen_to('camera0_rgba_nvmm')

# Set locations for new video recordings
for pipeline in pipelines_video_rec:
    pipeline.set_file_location('test_' + pipeline._name + '_1.mkv')

for pipeline in pipelines_video_enc:
    pipeline.play()

for pipeline in pipelines_video_rec:
    pipeline.play()

time.sleep(10)

# Send EOS event to encode pipelines for proper closing
# EOS to recording pipelines
for pipeline in pipelines_video_enc:
    pipeline.eos()
# Stop pipelines
for pipeline in pipelines_snap:
    pipeline.stop()
for pipeline in pipelines_video_rec:
    pipeline.stop()
for pipeline in pipelines_video_enc:
    pipeline.stop()
for pipeline in pipelines_base:
    pipeline.stop()

# Delete pipelines
for pipeline in pipelines_snap:
    pipeline.delete()
for pipeline in pipelines_video_rec:
    pipeline.delete()
for pipeline in pipelines_video_enc:
    pipeline.delete()
for pipeline in pipelines_base:
    pipeline.delete()
