import streamlit as st
from search_interface import search_images
from PIL import Image
import os

st.set_page_config(page_title="图像搜索系统", layout="wide")
st.title("媒体文件图像搜索")

st.sidebar.header("搜索条件")

# 条件输入
object_input = st.sidebar.text_input("包含物体（用逗号分隔）", "person, dog")
object_keywords = [x.strip() for x in object_input.split(",") if x.strip()]

has_faces = st.sidebar.selectbox("是否有人脸", ("不限", "有", "无"))
has_faces_flag = {"不限": None, "有": True, "无": False}[has_faces]

camera_model_like = st.sidebar.text_input("拍摄设备（模糊匹配）", "")
date_range = st.sidebar.date_input("拍摄时间范围", [])

start_date = str(date_range[0]) if len(date_range) >= 1 else None
end_date = str(date_range[1]) if len(date_range) == 2 else None
time_range = (start_date, end_date) if start_date and end_date else None

# 开始搜索
if st.sidebar.button("开始搜索"):
    st.write("正在搜索，请稍候...")

    results = search_images(
        object_keywords=object_keywords,
        has_faces=has_faces_flag,
        camera_model_like=camera_model_like,
        taken_time_range=time_range
    )

    st.success(f"共找到 {len(results)} 张图片")

    # 展示结果
    for path, model, time, objects, face in results:
        cols = st.columns([1, 2])
        try:
            if os.path.exists(path):
                img = Image.open(path)
                cols[0].image(img, use_column_width=True)
            else:
                cols[0].write("图片文件不存在")
        except Exception as e:
            cols[0].write(f"无法加载图片: {e}")

        info = f"""
        **路径**: `{path}`  
        **设备**: {model or '未知'}  
        **拍摄时间**: {time or '未知'}  
        **物体**: {objects or '无'}  
        **人脸**: {'有' if face else '无'}  
        """
        cols[1].markdown(info)

else:
    st.info("请在左侧设置搜索条件并点击“开始搜索”。")
