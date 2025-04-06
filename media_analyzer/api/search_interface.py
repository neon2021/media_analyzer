from media_analyzer.db.db_manager import get_db

def search_images(
    object_keywords=None,       # ['person', 'dog']
    has_faces=None,             # True / False / None
    camera_model_like=None,     # "iPhone"
    taken_time_range=None,      # ("2022-01-01", "2023-01-01")
    device_uuid=None            # 指定硬盘
):
    db = get_db()
    
    query = """
        SELECT f.path, i.camera_model, i.taken_time, i.objects, i.has_faces
        FROM image_analysis i
        JOIN files f ON i.file_id = f.id
        WHERE 1=1
    """
    params = []

    if object_keywords:
        placeholder = '%s' if db.db_type == 'postgres' else '?'
        for keyword in object_keywords:
            query += f" AND i.objects LIKE {placeholder}"
            params.append(f"%{keyword}%")

    if has_faces is not None:
        placeholder = '%s' if db.db_type == 'postgres' else '?'
        query += f" AND i.has_faces = {placeholder}"
        params.append(1 if has_faces else 0)

    if camera_model_like:
        placeholder = '%s' if db.db_type == 'postgres' else '?'
        query += f" AND i.camera_model LIKE {placeholder}"
        params.append(f"%{camera_model_like}%")

    if taken_time_range:
        placeholder = '%s' if db.db_type == 'postgres' else '?'
        start, end = taken_time_range
        query += f" AND i.taken_time BETWEEN {placeholder} AND {placeholder}"
        params.extend([start, end])

    if device_uuid:
        placeholder = '%s' if db.db_type == 'postgres' else '?'
        query += f" AND f.device_uuid = {placeholder}"
        params.append(device_uuid)

    db.execute(query, tuple(params))
    return db.fetch_all()
