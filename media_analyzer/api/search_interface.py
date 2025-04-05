from db_manager import get_db

def search_images(
    object_keywords=None,       # ['person', 'dog']
    has_faces=None,             # True / False / None
    camera_model_like=None,     # "iPhone"
    taken_time_range=None,      # ("2022-01-01", "2023-01-01")
    device_uuid=None            # 指定硬盘
):
    db = get_db()
    
    with db.get_cursor(commit=False) as cursor:
        query = """
            SELECT f.path, i.camera_model, i.taken_time, i.objects, i.has_faces
            FROM image_analysis i
            JOIN files f ON i.file_id = f.id
            WHERE 1=1
        """
        params = []

        if object_keywords:
            for keyword in object_keywords:
                query += " AND i.objects LIKE ?"
                params.append(f"%{keyword}%")

        if has_faces is not None:
            query += " AND i.has_faces = ?"
            params.append(1 if has_faces else 0)

        if camera_model_like:
            query += " AND i.camera_model LIKE ?"
            params.append(f"%{camera_model_like}%")

        if taken_time_range:
            start, end = taken_time_range
            query += " AND i.taken_time BETWEEN ? AND ?"
            params.extend([start, end])

        if device_uuid:
            query += " AND f.device_uuid = ?"
            params.append(device_uuid)

        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
