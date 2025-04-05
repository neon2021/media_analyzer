from setuptools import setup, find_packages

setup(
    name="media_analyzer",
    version="0.1.0",
    description="媒体文件分析和管理系统",
    author="Media Analyzer Team",
    author_email="example@example.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "psycopg2-binary",
        "pyyaml",
        "pillow",
        "numpy",
    ],
    entry_points={
        'console_scripts': [
            'media-scan=media_analyzer.scripts.scan:main',
            'media-analyze=media_analyzer.scripts.analyze:main',
        ],
    },
    python_requires='>=3.6',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
) 