from media_analyzer.api.search_interface import search_images

results = search_images(
    object_keywords=["dog", "car"],
    has_faces=True,
    camera_model_like="iPhone",
    taken_time_range=("2022-01-01", "2023-12-31")
)

for path, model, time, objects, face in results:
    print(f"{path} | {model} | {time} | {objects} | 人脸: {'有' if face else '无'}")
