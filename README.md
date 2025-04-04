```shell
conda activate tf-metal
```


```shell
pip install pillow exifread face_recognition torch torchvision
```

```shell
pip freeze | grep -Ei "pillow|exifread|face_recognition|torch|torchvision"

ExifRead==3.0.0
Pillow==10.0.0
torch==2.0.0
torchvision==0.15.1
```

## 准备：安装 YOLOv5 推理环境

```shell
pip install torch torchvision
pip install opencv-python

# 以下指令失败了
git clone https://github.com/ultralytics/yolov5.git
cd yolov5
pip install -r requirements.txt

# 在页面： https://github.com/ultralytics/yolov5/releases 下载 source zip: https://github.com/ultralytics/yolov5/archive/refs/tags/v7.0.zip

```

## 建表

```sql
CREATE TABLE IF NOT EXISTS image_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    camera_model TEXT,
    taken_time TEXT,
    gps_lat REAL,
    gps_lon REAL,
    has_faces INTEGER DEFAULT 0,
    objects TEXT,
    analyzed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

ALTER TABLE image_analysis ADD COLUMN objects TEXT;
```

## 安装UI开发组件

```shell
pip install streamlit
```

### 开发完毕 image_search_app.py 启动网页版 GUI

```shell
streamlit run image_search_app.py
```

